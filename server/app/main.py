"""FastAPI 入口。"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from . import __version__
from .cleanup import CleanupTask
from .config import get_settings
from .ratelimit import build_limiter
from .routes import register_routes
from .storage import build_storage


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    _setup_logging(settings.log_level)
    logger = logging.getLogger("agent-handoff")
    logger.info("starting agent-handoff v%s, storage=%s", __version__, settings.storage_backend)

    storage = build_storage(settings)
    app.state.storage = storage
    app.state.cleanup = CleanupTask(storage, settings.cleanup_interval)
    app.state.cleanup.start()

    try:
        yield
    finally:
        logger.info("shutting down")
        await app.state.cleanup.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    limiter = build_limiter()
    app = FastAPI(
        title="agent-handoff",
        version=__version__,
        description="End-to-end encrypted handoff bundle relay",
        lifespan=lifespan,
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    register_routes(app)
    return app


app = create_app()
