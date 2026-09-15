"""Serve the packaged React SPA without intercepting API routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

STATIC_DIR = Path(__file__).resolve().parent.parent / 'static'


def _inject_mount(html: str, mount_path: str) -> str:
    mount = mount_path.rstrip('/') or ''
    snippet = f'<script>window.__GITPULSE_MOUNT__={mount!r};</script>'
    if '</head>' in html:
        return html.replace('</head>', f'{snippet}</head>', 1)
    return snippet + html


def mount_static_ui(
    app: FastAPI,
    *,
    mount_path: str = '/git',
    static_dir: Path | None = None,
) -> None:
    """Mount hashed assets and an SPA fallback under `mount_path`."""

    root = static_dir or STATIC_DIR
    assets = root / 'assets'
    index = root / 'index.html'
    mount = mount_path.rstrip('/') or ''

    if assets.is_dir():
        app.mount(f'{mount}/assets', StaticFiles(directory=assets), name='gitpulse-assets')

    @app.get(f'{mount}/', response_class=HTMLResponse, include_in_schema=False)
    @app.get(f'{mount}', response_class=HTMLResponse, include_in_schema=False)
    async def spa_index() -> HTMLResponse:
        if not index.is_file():
            raise HTTPException(status_code=404, detail='UI not packaged')
        html = index.read_text(encoding='utf-8')
        return HTMLResponse(_inject_mount(html, mount))

    @app.get(f'{mount}/{{path:path}}', include_in_schema=False)
    async def spa_fallback(path: str, request: Request) -> Response:
        if path.startswith('api/') or path == 'api':
            raise HTTPException(status_code=404, detail='Not Found')
        if path.startswith('assets/'):
            raise HTTPException(status_code=404, detail='Asset not found')
        if not index.is_file():
            raise HTTPException(status_code=404, detail='UI not packaged')
        html = index.read_text(encoding='utf-8')
        return HTMLResponse(_inject_mount(html, mount))
