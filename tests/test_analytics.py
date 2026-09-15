"""Commit index, contribution metrics, filters, and trends."""

from __future__ import annotations

import subprocess
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from tests.conftest import commit_as

import gitpulse.analytics.index as index_module
from gitpulse.analytics import IndexCache, build_dashboard
from gitpulse.analytics.metrics import select_commit_shas
from gitpulse.git.errors import GitCommandError, UnknownAuthorError
from gitpulse.git.repository import GitRepository

NOW = datetime(2026, 3, 10, 12, 0, tzinfo=UTC)


def _index(repo_path: Path, **cache_kwargs: int):  # type: ignore[no-untyped-def]
    repo = GitRepository(repo_path)
    return IndexCache(**cache_kwargs).get(repo, 'main')


def test_index_excludes_merges_and_applies_mailmap(history_repo: Path) -> None:
    index = _index(history_repo)
    assert len(index) == 6
    assert sorted(index.author_names) == ['Ada Lovelace', 'Bob Builder']
    assert not index.truncated


def test_dashboard_shares_and_core_authors(history_repo: Path) -> None:
    board = build_dashboard(_index(history_repo), now=NOW)
    assert board.total_commits == 6
    assert board.author_count == 2
    assert [(row.name, row.commits) for row in board.contributors] == [
        ('Ada Lovelace', 4),
        ('Bob Builder', 2),
    ]
    assert board.contributors[0].share_percent == pytest.approx(66.67)
    assert board.core_authors == 1
    assert board.first_commit_at == datetime(2026, 1, 5, 7, 0, tzinfo=UTC)
    assert board.last_commit_at == datetime(2026, 3, 2, 9, 0, tzinfo=UTC)
    assert board.selected_author is None
    assert sum(map(sum, board.punchcard)) == 6


def test_weekly_trend_is_continuous(history_repo: Path) -> None:
    trend = build_dashboard(_index(history_repo), now=NOW).trend
    assert trend.granularity == 'week'
    starts = [bucket.start for bucket in trend.buckets]
    assert starts[0] == date(2026, 1, 5)
    assert starts[-1] == date(2026, 3, 9)
    assert all(b - a == timedelta(days=7) for a, b in zip(starts, starts[1:], strict=False))
    assert sum(bucket.commits for bucket in trend.buckets) == 6
    assert any(bucket.commits == 0 for bucket in trend.buckets)


def test_monthly_trend_labels(history_repo: Path) -> None:
    trend = build_dashboard(_index(history_repo), granularity='month', now=NOW).trend
    assert [(b.period, b.commits) for b in trend.buckets] == [
        ('2026-01', 3),
        ('2026-02', 2),
        ('2026-03', 1),
    ]


def test_author_filter_profile_and_punchcard(history_repo: Path) -> None:
    board = build_dashboard(_index(history_repo), author='BOB@example.com', now=NOW)
    profile = board.selected_author
    assert profile is not None
    assert (profile.name, profile.commits, profile.rank) == ('Bob Builder', 2, 2)
    assert profile.share_percent == pytest.approx(33.33)
    assert profile.active_periods == 2
    # Contributors stay the full picture; only focus metrics are filtered.
    assert board.total_commits == 6
    assert sum(b.author_commits or 0 for b in board.trend.buckets) == 2
    # 2026-01-07 23:30 at -05:00 is Wednesday 23h local; 2026-02-20 08:00 UTC is Friday 8h.
    assert board.punchcard[2][23] == 1
    assert board.punchcard[4][8] == 1
    assert sum(map(sum, board.punchcard)) == 2


def test_punchcard_uses_author_local_time(history_repo: Path) -> None:
    board = build_dashboard(_index(history_repo), author='ada@example.com', now=NOW)
    # 2026-01-05 10:00 at +03:00 is Monday 10h in Ada's local time (07h UTC).
    assert board.punchcard[0][10] == 1
    assert board.punchcard[0][7] == 0


def test_unknown_author_is_rejected(history_repo: Path) -> None:
    with pytest.raises(UnknownAuthorError):
        build_dashboard(_index(history_repo), author='nobody@example.com', now=NOW)


def test_since_window(history_repo: Path) -> None:
    board = build_dashboard(_index(history_repo), since=date(2026, 2, 1), now=NOW)
    assert board.total_commits == 3
    assert board.trend.buckets[0].start == date(2026, 1, 26)
    assert {row.name: row.commits for row in board.contributors} == {
        'Ada Lovelace': 2,
        'Bob Builder': 1,
    }


def test_top_n_folds_the_rest(history_repo: Path) -> None:
    board = build_dashboard(_index(history_repo), top=1, now=NOW)
    assert len(board.contributors) == 1
    assert (board.other_authors, board.other_commits) == (1, 2)
    assert board.other_share_percent == pytest.approx(33.33)


def test_select_commit_shas_by_author(history_repo: Path) -> None:
    repo = GitRepository(history_repo)
    index = IndexCache().get(repo, 'main')
    shas = select_commit_shas(index, author='bob@example.com')
    commits = repo.show_commits(shas)
    assert [c.subject for c in commits] == ['feat: b2', 'fix: b1']
    assert select_commit_shas(index, author='bob@example.com', skip=1, limit=5) == shas[1:]


def test_cache_invalidates_on_new_tip(history_repo: Path) -> None:
    repo = GitRepository(history_repo)
    cache = IndexCache()
    first = cache.get(repo, 'main')
    assert cache.get(repo, 'main') is first
    commit_as(history_repo, 'Bob Builder', 'bob@example.com', '2026-03-05T10:00:00+00:00', 'x')
    second = cache.get(repo, 'main')
    assert second is not first
    assert len(second) == 7


def test_scan_limit_marks_truncation(history_repo: Path) -> None:
    index = _index(history_repo, max_commits=2)
    assert len(index) == 2
    assert index.truncated
    assert build_dashboard(index, now=NOW).truncated


def test_summary_first_commit_is_the_root(history_repo: Path) -> None:
    summary = GitRepository(history_repo).summary()
    assert summary.first_commit_at is not None
    assert summary.first_commit_at.astimezone(UTC) == datetime(2026, 1, 5, 7, 0, tzinfo=UTC)
    assert summary.last_commit_at is not None
    assert summary.last_commit_at.astimezone(UTC) == datetime(2026, 3, 2, 9, 0, tzinfo=UTC)


def test_bare_blobless_clone_keeps_mailmap(history_repo: Path, tmp_path: Path) -> None:
    bare = tmp_path / 'bare.git'
    subprocess.run(
        ['git', 'clone', '--bare', '--no-local', str(history_repo), str(bare)],
        check=True,
        capture_output=True,
    )
    index = IndexCache().get(GitRepository(bare), 'main')
    assert sorted(index.author_names) == ['Ada Lovelace', 'Bob Builder']


def test_failed_build_is_retried(history_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = GitRepository(history_repo)
    cache = IndexCache()
    real_build = index_module.build_index
    calls = 0

    def flaky_build(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        if calls == 1:
            raise GitCommandError('git timed out')
        return real_build(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(index_module, 'build_index', flaky_build)
    with pytest.raises(GitCommandError):
        cache.get(repo, 'main')
    assert not cache._building
    assert len(cache.get(repo, 'main')) == 6
    assert calls == 2
