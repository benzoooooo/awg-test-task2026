"""FastAPI integration for AWG GitPulse."""

from gitpulse.fastapi_app.factory import create_app, create_router
from gitpulse.fastapi_app.static import mount_static_ui

__all__ = ['create_app', 'create_router', 'mount_static_ui']
