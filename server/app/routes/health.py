"""健康检查。"""
from __future__ import annotations

from fastapi import APIRouter, Request

from .. import __version__
from ..models import HealthResponse
from ..storage import StorageBackend

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    storage: StorageBackend = request.app.state.storage
    return HealthResponse(status="ok", storage=storage.name, version=__version__)
