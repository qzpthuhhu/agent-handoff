"""基于 slowapi 的速率限制。

默认按 IP 限速,上传/拉取共享一个桶。
"""
from __future__ import annotations

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from .config import Settings, get_settings


def _limit_key(request: Request) -> str:
    # 简单用 remote addr
    return get_remote_address(request)


def build_limiter() -> Limiter:
    settings: Settings = get_settings()
    return Limiter(
        key_func=_limit_key,
        default_limits=[f"{settings.rate_limit_per_min}/minute"],
    )
