"""应用配置(从环境变量读)。"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 服务
    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "INFO"

    # 存储
    storage_backend: str = Field(default="local", description="local | tos")
    local_storage_dir: Path = Path("/var/lib/agent-handoff/bundles")
    local_index_db: Path = Path("/var/lib/agent-handoff/index.sqlite")

    tos_endpoint: str = "tos-cn-beijing.volces.com"
    tos_region: str = "cn-beijing"
    tos_bucket: str = "agent-handoff"
    tos_access_key: str = ""
    tos_secret_key: str = ""
    tos_prefix: str = "bundles"

    # 索引
    enable_index: bool = True

    # 业务
    max_bundle_size: int = 50 * 1024 * 1024  # 50MB
    default_expires_in: int = 7 * 24 * 3600
    one_time_consume: bool = False
    bundle_id_length: int = 32

    # 安全
    admin_token: str = "change-me-to-a-long-random-string"

    # 限速
    rate_limit_per_min: int = 30

    # 清理
    cleanup_interval: int = 6 * 3600


@lru_cache
def get_settings() -> Settings:
    return Settings()
