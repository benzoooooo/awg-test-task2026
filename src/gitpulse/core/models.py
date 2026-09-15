"""Pure domain types."""

from __future__ import annotations

from datetime import datetime

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
