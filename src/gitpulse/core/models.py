"""Pure domain types."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class Author(BaseModel):
    """Canonical author identity after mailmap resolution."""

    name: str
    email: str
    commits: int = 0


class BranchRef(BaseModel):
    """Local branch tip."""

    name: str
    tip_sha: str
    tip_date: datetime | None = None
    tip_author: str | None = None


class Commit(BaseModel):
    """Single commit metadata (no patch body)."""

    sha: str
    short_sha: str
    author_name: str
    author_email: str
    authored_at: datetime
    subject: str


class RepoSummary(BaseModel):
    """Repository header shown in the UI."""

    path: str
    head: str | None = None
    default_branch: str | None = None
    commit_count: int = 0
    first_commit_at: datetime | None = None
    last_commit_at: datetime | None = None
    branch_count: int = 0
    author_count: int = 0


class AuthorContribution(BaseModel):
    """Author share of project activity."""

    name: str
    email: str
    commits: int
    insertions: int = 0
    deletions: int = 0
    share_percent: float = Field(ge=0.0)


class ActivityBucket(BaseModel):
    """Commits aggregated into a time bucket."""

    period: str
    commits: int


class RepoSource(StrEnum):
    """Where an analyzable repository comes from."""

    LOCAL = 'local'
    REMOTE = 'remote'


class RepoStatus(StrEnum):
    """Lifecycle of a registered repository."""

    PENDING = 'pending'
    CLONING = 'cloning'
    READY = 'ready'
    FAILED = 'failed'


class RepoInfo(BaseModel):
    """Registered repository and its clone / refresh state."""

    id: str
    name: str
    url: str | None = None
    source: RepoSource
    status: RepoStatus
    error: str | None = None
    refreshing: bool = False
    pinned: bool = False
    created_at: datetime
    updated_at: datetime
    fetched_at: datetime | None = None
    size_bytes: int | None = None


class TrendBucket(BaseModel):
    """Commits in one calendar week or month (UTC, by author date)."""

    period: str
    start: date
    commits: int
    author_commits: int | None = None
    active_authors: int


class Trend(BaseModel):
    """Continuous activity series; empty periods are included as zeros."""

    granularity: Literal['week', 'month']
    buckets: list[TrendBucket]


class AuthorProfile(BaseModel):
    """Activity of one author inside the analyzed window."""

    name: str
    email: str
    commits: int
    share_percent: float = Field(ge=0.0)
    rank: int | None = None
    first_commit_at: datetime | None = None
    last_commit_at: datetime | None = None
    active_periods: int
    total_periods: int


class Dashboard(BaseModel):
    """Everything the contribution dashboard renders for one branch and window."""

    branch: str
    tip_sha: str
    since: date | None = None
    author: str | None = None
    total_commits: int
    author_count: int
    first_commit_at: datetime | None = None
    last_commit_at: datetime | None = None
    core_authors: int
    scanned_commits: int
    truncated: bool
    contributors: list[AuthorContribution]
    other_authors: int
    other_commits: int
    other_share_percent: float = Field(ge=0.0)
    trend: Trend
    punchcard: list[list[int]]
    selected_author: AuthorProfile | None = None
