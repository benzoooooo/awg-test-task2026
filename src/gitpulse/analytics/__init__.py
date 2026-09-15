"""Contribution and activity analytics over mailmap-resolved commit metadata."""

from __future__ import annotations

from datetime import date

from gitpulse.analytics.index import CommitIndex, IndexCache, build_index
from gitpulse.analytics.metrics import (
    build_dashboard,
    contributions_for,
    select_rows,
    weekly_activity,
)
from gitpulse.core.models import ActivityBucket, AuthorContribution
from gitpulse.git.repository import GitRepository

_DEFAULT_CACHE = IndexCache()

__all__ = [
    'CommitIndex',
    'IndexCache',
    'activity_by_week',
    'author_contributions',
    'build_dashboard',
    'build_index',
]


def author_contributions(
    repo: GitRepository,
    *,
    branch: str | None = None,
    limit_commits: int = 500,
    since: date | None = None,
    cache: IndexCache | None = None,
) -> list[AuthorContribution]:
    """Commit-count share over the newest `limit_commits` commits of a branch (mailmap-aware).

    Line-based accounting needs file contents, which blobless clones do not keep;
    commit counts are the documented baseline (see ADR 0002 / 0004).
    """

    index = (cache or _DEFAULT_CACHE).get(repo, branch or repo.head_branch())
    return contributions_for(index, select_rows(index, since=since, limit=limit_commits))


def activity_by_week(
    repo: GitRepository,
    *,
    branch: str | None = None,
    limit_commits: int = 500,
    since: date | None = None,
    author: str | None = None,
    cache: IndexCache | None = None,
) -> list[ActivityBucket]:
    """Bucket the newest `limit_commits` commits by ISO week, optionally for one author."""

    index = (cache or _DEFAULT_CACHE).get(repo, branch or repo.head_branch())
    author_id = index.find_author(author) if author else None
    rows = select_rows(index, since=since, author_id=author_id, limit=limit_commits)
    return weekly_activity(index, rows)
