"""Application and router factories."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, FastAPI

from gitpulse import __version__
from gitpulse.analytics import IndexCache
from gitpulse.fastapi_app.routes import build_api_router
from gitpulse.fastapi_app.static import mount_static_ui
from gitpulse.git.registry import RepoRegistry
from gitpulse.git.repository import GitRepository
from gitpulse.settings import GitPulseSettings


def create_router(
    *,
    mount_path: str = '/git',
    api_prefix: str = '/api/v1',
    repo_path: Path | str | None = None,
    settings: GitPulseSettings | None = None,
) -> APIRouter:
    """Build the API router mounted by the host under `mount_path`.

    `repo_path` exposes one local repository. Remote repositories are enabled with
    `settings.remote_enabled` (or `GITPULSE_REMOTE_ENABLED=true`); at least one of
    the two is required.
    """

    config = settings or GitPulseSettings()
    repository = (
        GitRepository(repo_path, log_timeout=config.log_timeout_sec)
        if repo_path is not None
        else None
    )
    registry: RepoRegistry | None = None
    if config.remote_enabled:
        registry = RepoRegistry(config)
        if repository is not None:
            registry.add_local(repository)
    if repository is None and registry is None:
        raise ValueError('repo_path is required unless remote repositories are enabled')
    router = build_api_router(
        repository,
        api_prefix=api_prefix,
        registry=registry,
        index_cache=IndexCache(
            max_entries=config.index_cache_size,
            max_commits=config.max_commits_scan,
        ),
        settings=config,
    )
    if registry is not None:
        registry.preload(config.preload_url_list)
    return router


def create_app(
    *,
    mount_path: str = '/git',
    api_prefix: str = '/api/v1',
    repo_path: Path | str | None = None,
    mount_ui: bool = True,
    settings: GitPulseSettings | None = None,
) -> FastAPI:
    """Convenience FastAPI app used by the fixture host and demos."""

    app = FastAPI(title='AWG GitPulse', version=__version__)
    router = create_router(
        mount_path=mount_path,
        api_prefix=api_prefix,
        repo_path=repo_path,
        settings=settings,
    )
    app.include_router(router, prefix=mount_path)
    if mount_ui:
        mount_static_ui(app, mount_path=mount_path)
    return app
