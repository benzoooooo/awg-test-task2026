"""Application and router factories."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, FastAPI

from gitpulse.fastapi_app.routes import build_api_router
from gitpulse.fastapi_app.static import mount_static_ui
from gitpulse.git.repository import GitRepository


def create_router(
    *,
    mount_path: str = '/git',
    api_prefix: str = '/api/v1',
    repo_path: Path | str | None = None,
) -> APIRouter:
    """Build the API router mounted by the host under `mount_path`."""

    if repo_path is None:
        raise ValueError('repo_path is required')
    repository = GitRepository(repo_path)
    return build_api_router(repository, api_prefix=api_prefix)


def create_app(
    *,
    mount_path: str = '/git',
    api_prefix: str = '/api/v1',
    repo_path: Path | str | None = None,
    mount_ui: bool = True,
) -> FastAPI:
    """Convenience FastAPI app used by the fixture host and demos."""

    app = FastAPI(title='AWG GitPulse', version='0.1.0')
    router = create_router(mount_path=mount_path, api_prefix=api_prefix, repo_path=repo_path)
    app.include_router(router, prefix=mount_path)
    if mount_ui:
        mount_static_ui(app, mount_path=mount_path)
    return app
