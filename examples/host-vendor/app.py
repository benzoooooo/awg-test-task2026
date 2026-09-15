"""Host that installs GitPulse from a vendored wheel."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI

from gitpulse.fastapi_app import create_router, mount_static_ui

REPO = Path(os.environ.get('GITPULSE_REPO_PATH', Path.cwd()))

app = FastAPI(title='GitPulse vendor host')
app.include_router(create_router(mount_path='/git', repo_path=REPO), prefix='/git')
mount_static_ui(app, mount_path='/git')


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok', 'host': 'vendor'}
