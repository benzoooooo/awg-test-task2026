"""Minimal host application mounting AWG GitPulse under `/git`."""

from __future__ import annotations

import os
from pathlib import Path

from gitpulse.fastapi_app import create_app
from gitpulse.settings import GitPulseSettings

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPO = Path(os.environ.get('GITPULSE_REPO_PATH', str(ROOT)))

os.environ.setdefault('GITPULSE_REMOTE_ENABLED', 'true')
os.environ.setdefault('GITPULSE_DATA_DIR', str(ROOT / '.gitpulse-data'))


def build_host_app():
    app = create_app(
        mount_path='/git',
        repo_path=DEFAULT_REPO,
        mount_ui=True,
        settings=GitPulseSettings(),
    )

    @app.get('/health')
    def host_health() -> dict[str, str]:
        return {'status': 'ok', 'host': 'fixture'}

    return app


app = build_host_app()
