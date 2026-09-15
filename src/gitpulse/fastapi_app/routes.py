"""REST routes: repository registry, repository metadata, and contribution analytics.

This module intentionally does not use postponed annotations: FastAPI must evaluate
`Annotated[..., Depends(resolver)]` signatures that close over local resolvers.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi import Path as PathParam
from pydantic import BaseModel, Field

from gitpulse import __version__
from gitpulse.analytics import IndexCache, activity_by_week, author_contributions
from gitpulse.analytics.metrics import (
    authors_for,
    build_dashboard,
    select_commit_shas,
    select_rows,
)
from gitpulse.core.models import (
    ActivityBucket,
    Author,
    AuthorContribution,
    BranchRef,
    Commit,
    Dashboard,
    RepoInfo,
    RepoSource,
    RepoStatus,
    RepoSummary,
)
from gitpulse.git.errors import (
    GitPulseError,
    InvalidRemoteUrlError,
    RepositoryLimitError,
    RepositoryNotReadyError,
    UnknownAuthorError,
    UnknownRefError,
    UnknownRepositoryError,
)
from gitpulse.git.registry import LOCAL_REPO_ID, RepoRegistry
from gitpulse.git.repository import GitRepository
from gitpulse.settings import GitPulseSettings

REPO_ID_PATTERN = r'^(local|[0-9a-f]{16})$'


class ConnectRepoRequest(BaseModel):
    url: str = Field(
        min_length=1,
        max_length=2048,
        examples=['https://github.com/fastapi/fastapi'],
    )


class ServiceConfig(BaseModel):
    version: str
    remote_enabled: bool
    allowed_hosts: list[str]
    max_repos: int
    max_repo_size_mb: int
    max_commits_scan: int


@contextmanager
def _http_errors() -> Iterator[None]:
    try:
        yield
    except (UnknownRefError, UnknownAuthorError, UnknownRepositoryError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RepositoryNotReadyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidRemoteUrlError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except RepositoryLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except GitPulseError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def build_api_router(
    repository: GitRepository | None = None,
    *,
    api_prefix: str = '/api/v1',
    registry: RepoRegistry | None = None,
    index_cache: IndexCache | None = None,
    settings: GitPulseSettings | None = None,
) -> APIRouter:
    if repository is None and registry is None:
        raise ValueError('a repository or a registry is required')
    cache = index_cache or IndexCache()
    config = settings or GitPulseSettings()
    started_at = datetime.now(tz=UTC)
    router = APIRouter(prefix=api_prefix, tags=['gitpulse'])

    def local_info() -> RepoInfo:
        if repository is None:
            raise UnknownRepositoryError(f'unknown repository: {LOCAL_REPO_ID}')
        return RepoInfo(
            id=LOCAL_REPO_ID,
            name=repository.path.name,
            source=RepoSource.LOCAL,
            status=RepoStatus.READY,
            pinned=True,
            created_at=started_at,
            updated_at=started_at,
        )

    def resolve_repository(
        repo_id: Annotated[str, PathParam(pattern=REPO_ID_PATTERN)],
    ) -> GitRepository:
        with _http_errors():
            if registry is not None:
                return registry.open(repo_id)
            if repo_id == LOCAL_REPO_ID and repository is not None:
                return repository
            raise UnknownRepositoryError(f'unknown repository: {repo_id}')

    if registry is not None:

        def warm_index(_repo_id: str, repo: GitRepository) -> None:
            cache.get(repo, repo.head_branch())

        registry.add_ready_listener(warm_index)

    @router.get('/health')
    def health() -> dict[str, str]:
        return {'status': 'ok', 'version': __version__}

    @router.get('/config', response_model=ServiceConfig)
    def service_config() -> ServiceConfig:
        return ServiceConfig(
            version=__version__,
            remote_enabled=registry is not None,
            allowed_hosts=sorted(config.allowed_host_set),
            max_repos=config.max_repos,
            max_repo_size_mb=config.max_repo_size_mb,
            max_commits_scan=config.max_commits_scan,
        )

    @router.get('/repos', response_model=list[RepoInfo])
    def list_repos() -> list[RepoInfo]:
        if registry is not None:
            return registry.list_repos()
        return [local_info()]

    @router.post('/repos', response_model=RepoInfo, status_code=status.HTTP_202_ACCEPTED)
    def connect_repo(body: ConnectRepoRequest) -> RepoInfo:
        if registry is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='remote repositories are disabled on this server',
            )
        with _http_errors():
            return registry.connect(body.url)

    @router.get('/repos/{repo_id}', response_model=RepoInfo)
    def get_repo(repo_id: Annotated[str, PathParam(pattern=REPO_ID_PATTERN)]) -> RepoInfo:
        with _http_errors():
            if registry is not None:
                return registry.get(repo_id)
            return local_info()

    @router.post(
        '/repos/{repo_id}/refresh',
        response_model=RepoInfo,
        status_code=status.HTTP_202_ACCEPTED,
    )
    def refresh_repo(repo_id: Annotated[str, PathParam(pattern=REPO_ID_PATTERN)]) -> RepoInfo:
        with _http_errors():
            if registry is not None:
                return registry.refresh(repo_id)
            return local_info()

    if repository is not None:
        fixed_repository = repository
        _add_repository_routes(router, '', lambda: fixed_repository, cache)
    _add_repository_routes(router, '/repos/{repo_id}', resolve_repository, cache)
    return router


def _add_repository_routes(
    router: APIRouter,
    prefix: str,
    resolve: Callable[..., GitRepository],
    cache: IndexCache,
) -> None:
    """Register read endpoints for one repository resolver under `prefix`."""

    @router.get(f'{prefix}/summary', response_model=RepoSummary)
    def summary(repository: Annotated[GitRepository, Depends(resolve)]) -> RepoSummary:
        with _http_errors():
            return repository.summary()

    @router.get(f'{prefix}/branches', response_model=list[BranchRef])
    def branches(repository: Annotated[GitRepository, Depends(resolve)]) -> list[BranchRef]:
        with _http_errors():
            return repository.list_branches()

    @router.get(f'{prefix}/commits', response_model=list[Commit])
    def commits(
        repository: Annotated[GitRepository, Depends(resolve)],
        branch: str = Query(..., min_length=1),
        limit: int = Query(default=50, ge=1, le=200),
        skip: int = Query(default=0, ge=0),
        author: str | None = Query(default=None, min_length=1, max_length=320),
        since: date | None = None,
    ) -> list[Commit]:
        with _http_errors():
            if author is None and since is None:
                return repository.list_commits(branch, limit=limit, skip=skip)
            index = cache.get(repository, branch)
            shas = select_commit_shas(index, since=since, author=author, skip=skip, limit=limit)
            return repository.show_commits(shas)

    @router.get(f'{prefix}/authors', response_model=list[Author])
    def authors(
        repository: Annotated[GitRepository, Depends(resolve)],
        branch: str | None = Query(default=None, min_length=1),
        since: date | None = None,
    ) -> list[Author]:
        with _http_errors():
            if branch is None and since is None:
                return repository.list_authors()
            index = cache.get(repository, branch or repository.head_branch())
            return authors_for(index, select_rows(index, since=since))

    @router.get(f'{prefix}/contributions', response_model=list[AuthorContribution])
    def contributions(
        repository: Annotated[GitRepository, Depends(resolve)],
        branch: str | None = None,
        limit_commits: int = Query(default=500, ge=1, le=2000),
        since: date | None = None,
    ) -> list[AuthorContribution]:
        with _http_errors():
            return author_contributions(
                repository,
                branch=branch,
                limit_commits=limit_commits,
                since=since,
                cache=cache,
            )

    @router.get(f'{prefix}/activity', response_model=list[ActivityBucket])
    def activity(
        repository: Annotated[GitRepository, Depends(resolve)],
        branch: str | None = None,
        limit_commits: int = Query(default=500, ge=1, le=2000),
        since: date | None = None,
        author: str | None = Query(default=None, min_length=1, max_length=320),
    ) -> list[ActivityBucket]:
        with _http_errors():
            return activity_by_week(
                repository,
                branch=branch,
                limit_commits=limit_commits,
                since=since,
                author=author,
                cache=cache,
            )

    @router.get(f'{prefix}/dashboard', response_model=Dashboard)
    def dashboard(
        repository: Annotated[GitRepository, Depends(resolve)],
        branch: str | None = Query(default=None, min_length=1),
        since: date | None = None,
        author: str | None = Query(default=None, min_length=1, max_length=320),
        granularity: Literal['auto', 'week', 'month'] = 'auto',
        top: int = Query(default=12, ge=1, le=100),
    ) -> Dashboard:
        with _http_errors():
            index = cache.get(repository, branch or repository.head_branch())
            return build_dashboard(
                index,
                since=since,
                author=author,
                granularity=granularity,
                top=top,
            )
