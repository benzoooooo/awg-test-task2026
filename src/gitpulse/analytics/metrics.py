"""Contribution and activity metrics over a commit index. Pure computation, no I/O."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from gitpulse.analytics.index import CommitIndex
from gitpulse.core.models import (
    ActivityBucket,
    Author,
    AuthorContribution,
    AuthorProfile,
    Dashboard,
    Trend,
    TrendBucket,
)

Granularity = Literal['auto', 'week', 'month']
AUTO_MONTH_THRESHOLD_DAYS = 548
SECONDS_PER_DAY = 86_400
EPOCH_ORDINAL = date(1970, 1, 1).toordinal()
EPOCH_WEEKDAY = 3  # 1970-01-01 was a Thursday (Monday = 0)
CORE_SHARE = 0.5


def _day_of(timestamp: int) -> date:
    return date.fromordinal(EPOCH_ORDINAL + timestamp // SECONDS_PER_DAY)


def _ts_of(day: date) -> int:
    return (day.toordinal() - EPOCH_ORDINAL) * SECONDS_PER_DAY


def _dt_of(timestamp: int) -> datetime:
    return datetime.fromtimestamp(timestamp, tz=UTC)


def select_rows(
    index: CommitIndex,
    *,
    since: date | None = None,
    author_id: int | None = None,
    limit: int | None = None,
) -> list[int]:
    """Row numbers (newest first) matching the window and author filter."""

    since_ts = _ts_of(since) if since is not None else None
    timestamps = index.timestamps
    author_ids = index.author_ids
    rows: list[int] = []
    for row in range(len(index)):
        if since_ts is not None and timestamps[row] < since_ts:
            continue
        if author_id is not None and author_ids[row] != author_id:
            continue
        rows.append(row)
        if limit is not None and len(rows) >= limit:
            break
    return rows


def ranked_authors(index: CommitIndex, rows: list[int]) -> list[tuple[int, int]]:
    """(author id, commits) sorted by commits desc, then name."""

    counts = Counter(index.author_ids[row] for row in rows)
    return sorted(counts.items(), key=lambda item: (-item[1], index.author_names[item[0]].lower()))


def contributions_for(index: CommitIndex, rows: list[int]) -> list[AuthorContribution]:
    total = len(rows)
    return [
        AuthorContribution(
            name=index.author_names[author_id],
            email=index.author_emails[author_id],
            commits=commits,
            share_percent=_share(commits, total),
        )
        for author_id, commits in ranked_authors(index, rows)
    ]


def authors_for(index: CommitIndex, rows: list[int]) -> list[Author]:
    return [
        Author(
            name=index.author_names[author_id],
            email=index.author_emails[author_id],
            commits=commits,
        )
        for author_id, commits in ranked_authors(index, rows)
    ]


def select_commit_shas(
    index: CommitIndex,
    *,
    since: date | None = None,
    author: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[str]:
    author_id = index.find_author(author) if author else None
    rows = select_rows(index, since=since, author_id=author_id, limit=skip + limit)
    return [index.shas[row] for row in rows[skip:]]


def core_author_count(ranked: list[tuple[int, int]], total: int) -> int:
    """Smallest number of top authors whose commits reach half of all commits."""

    if total <= 0:
        return 0
    covered = 0
    for position, (_author_id, commits) in enumerate(ranked, start=1):
        covered += commits
        if covered >= total * CORE_SHARE:
            return position
    return len(ranked)


def _bucket_start(day: date, granularity: Literal['week', 'month']) -> date:
    if granularity == 'week':
        return day - timedelta(days=day.weekday())
    return day.replace(day=1)


def _next_start(start: date, granularity: Literal['week', 'month']) -> date:
    if granularity == 'week':
        return start + timedelta(days=7)
    if start.month == 12:
        return date(start.year + 1, 1, 1)
    return date(start.year, start.month + 1, 1)


def _period_label(start: date, granularity: Literal['week', 'month']) -> str:
    if granularity == 'week':
        iso = start.isocalendar()
        return f'{iso.year}-W{iso.week:02d}'
    return f'{start.year}-{start.month:02d}'


def build_trend(
    index: CommitIndex,
    rows: list[int],
    *,
    since: date | None,
    today: date,
    author_id: int | None = None,
    granularity: Granularity = 'auto',
) -> Trend:
    """Continuous series from the window start to today; empty periods are zeros."""

    if not rows:
        return Trend(granularity='month' if granularity == 'month' else 'week', buckets=[])
    timestamps = index.timestamps
    author_ids = index.author_ids
    first_day = _day_of(min(timestamps[row] for row in rows))
    last_day = _day_of(max(timestamps[row] for row in rows))
    start_day = since if since is not None else first_day
    end_day = max(last_day, today)
    resolved: Literal['week', 'month']
    if granularity == 'auto':
        long_span = (end_day - start_day).days > AUTO_MONTH_THRESHOLD_DAYS
        resolved = 'month' if long_span else 'week'
    else:
        resolved = granularity

    totals: Counter[date] = Counter()
    mine: Counter[date] = Counter()
    active: defaultdict[date, set[int]] = defaultdict(set)
    starts: dict[int, date] = {}
    for row in rows:
        day_number = timestamps[row] // SECONDS_PER_DAY
        bucket = starts.get(day_number)
        if bucket is None:
            bucket = _bucket_start(_day_of(timestamps[row]), resolved)
            starts[day_number] = bucket
        totals[bucket] += 1
        active[bucket].add(author_ids[row])
        if author_id is not None and author_ids[row] == author_id:
            mine[bucket] += 1

    buckets: list[TrendBucket] = []
    cursor = _bucket_start(start_day, resolved)
    while cursor <= end_day:
        buckets.append(
            TrendBucket(
                period=_period_label(cursor, resolved),
                start=cursor,
                commits=totals.get(cursor, 0),
                author_commits=mine.get(cursor, 0) if author_id is not None else None,
                active_authors=len(active.get(cursor, ())),
            )
        )
        cursor = _next_start(cursor, resolved)
    return Trend(granularity=resolved, buckets=buckets)


def build_punchcard(index: CommitIndex, rows: list[int]) -> list[list[int]]:
    """7x24 commit counts by weekday (Monday = 0) and hour in each author's local time."""

    grid = [[0] * 24 for _ in range(7)]
    timestamps = index.timestamps
    offsets = index.offsets
    for row in rows:
        local = timestamps[row] + offsets[row] * 60
        days, seconds = divmod(local, SECONDS_PER_DAY)
        grid[(days + EPOCH_WEEKDAY) % 7][seconds // 3600] += 1
    return grid


def build_dashboard(
    index: CommitIndex,
    *,
    since: date | None = None,
    author: str | None = None,
    granularity: Granularity = 'auto',
    top: int = 15,
    now: datetime | None = None,
) -> Dashboard:
    today = (now or datetime.now(tz=UTC)).astimezone(UTC).date()
    author_id = index.find_author(author) if author else None
    window = select_rows(index, since=since)
    total = len(window)
    ranked = ranked_authors(index, window)
    top_ranked = ranked[:top]
    rest = ranked[top:]
    other_commits = sum(commits for _author_id, commits in rest)
    timestamps = index.timestamps

    focus = window
    if author_id is not None:
        focus = [row for row in window if index.author_ids[row] == author_id]
    trend = build_trend(
        index,
        window,
        since=since,
        today=today,
        author_id=author_id,
        granularity=granularity,
    )

    profile = None
    if author_id is not None:
        rank = next(
            (pos for pos, (aid, _commits) in enumerate(ranked, start=1) if aid == author_id),
            None,
        )
        profile = AuthorProfile(
            name=index.author_names[author_id],
            email=index.author_emails[author_id],
            commits=len(focus),
            share_percent=_share(len(focus), total),
            rank=rank,
            first_commit_at=_dt_of(min(timestamps[row] for row in focus)) if focus else None,
            last_commit_at=_dt_of(max(timestamps[row] for row in focus)) if focus else None,
            active_periods=sum(1 for bucket in trend.buckets if bucket.author_commits),
            total_periods=len(trend.buckets),
        )

    return Dashboard(
        branch=index.branch,
        tip_sha=index.tip_sha,
        since=since,
        author=author,
        total_commits=total,
        author_count=len(ranked),
        first_commit_at=_dt_of(min(timestamps[row] for row in window)) if window else None,
        last_commit_at=_dt_of(max(timestamps[row] for row in window)) if window else None,
        core_authors=core_author_count(ranked, total),
        scanned_commits=len(index),
        truncated=index.truncated,
        contributors=[
            AuthorContribution(
                name=index.author_names[aid],
                email=index.author_emails[aid],
                commits=commits,
                share_percent=_share(commits, total),
            )
            for aid, commits in top_ranked
        ],
        other_authors=len(rest),
        other_commits=other_commits,
        other_share_percent=_share(other_commits, total),
        trend=trend,
        punchcard=build_punchcard(index, focus),
        selected_author=profile,
    )


def weekly_activity(index: CommitIndex, rows: list[int]) -> list[ActivityBucket]:
    """Non-empty ISO weeks, oldest first (legacy `/activity` shape)."""

    counts: Counter[str] = Counter()
    for row in rows:
        iso = _day_of(index.timestamps[row]).isocalendar()
        counts[f'{iso.year}-W{iso.week:02d}'] += 1
    return [
        ActivityBucket(period=period, commits=count) for period, count in sorted(counts.items())
    ]


def _share(part: int, total: int) -> float:
    return round(100.0 * part / total, 2) if total else 0.0
