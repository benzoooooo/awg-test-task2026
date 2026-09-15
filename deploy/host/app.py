"""Production host: mounts AWG GitPulse from the installed wheel under `/git`."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from gitpulse.fastapi_app import create_router, mount_static_ui
from gitpulse.settings import GitPulseSettings

MOUNT_PATH = '/git'

settings = GitPulseSettings()
app = FastAPI(title='AWG GitPulse host', docs_url=None, redoc_url=None)
app.include_router(create_router(mount_path=MOUNT_PATH, settings=settings), prefix=MOUNT_PATH)
mount_static_ui(app, mount_path=MOUNT_PATH)


@app.get('/', include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(f'{MOUNT_PATH}/')


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok', 'host': 'deploy'}
