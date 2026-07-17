"""路由注册。"""
from fastapi import FastAPI

from . import bundles, health, install


def register_routes(app: FastAPI) -> None:
    app.include_router(health.router)
    app.include_router(bundles.router)
    app.include_router(install.router)
