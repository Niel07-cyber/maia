"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from maia.api import chat, demo, health
from maia.config import get_settings


def create_app() -> FastAPI:
    """Build the application. A factory makes it easy to create fresh apps in tests."""
    settings = get_settings()
    app = FastAPI(title="MAIA", description="Maintenance AI Assistant", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(demo.router)
    return app


app = create_app()
