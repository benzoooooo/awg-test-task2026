"""REST routes for repository metadata."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from gitpulse import __version__
from gitpulse.analytics import activity_by_week, author_contributions
from gitpulse.core.models import (
    ActivityBucket,
    Author,
    AuthorContribution,
    BranchRef,
    Commit,
    RepoSummary,
)
from gitpulse.git.errors import GitPulseError, UnknownRefError
from gitpulse.git.repository import GitRepository


def build_api_router(repository: GitRepository, *, api_prefix: str = '/api/v1') -> APIRouter:
    router = APIRouter(prefix=api_prefix, tags=['gitpulse'])

    @router.get('/health')
    def health() -> dict[str, str]:
        return {'status': 'ok', 'version': __version__}

    @router.get('/summary', response_model=RepoSummary)
    def summary() -> RepoSummary:
        try:
            return repository.summary()
        except GitPulseError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get('/branches', response_model=list[BranchRef])
    def branches() -> list[BranchRef]:
        try:
            return repository.list_branches()
        except GitPulseError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get('/commits', response_model=list[Commit])
    def commits(
        branch: str = Query(..., min_length=1),
        limit: int = Query(default=50, ge=1, le=200),
        skip: int = Query(default=0, ge=0),
    ) -> list[Commit]:
        try:
            return repository.list_commits(branch, limit=limit, skip=skip)
        except UnknownRefError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except GitPulseError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get('/authors', response_model=list[Author])
    def authors() -> list[Author]:
        try:
            return repository.list_authors()
        except GitPulseError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get('/contributions', response_model=list[AuthorContribution])
    def contributions(
        branch: str | None = None,
        limit_commits: int = Query(default=500, ge=1, le=2000),
    ) -> list[AuthorContribution]:
        try:
            return author_contributions(repository, branch=branch, limit_commits=limit_commits)
        except UnknownRefError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except GitPulseError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get('/activity', response_model=list[ActivityBucket])
    def activity(
        branch: str | None = None,
        limit_commits: int = Query(default=500, ge=1, le=2000),
    ) -> list[ActivityBucket]:
        try:
            return activity_by_week(repository, branch=branch, limit_commits=limit_commits)
        except UnknownRefError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except GitPulseError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router
