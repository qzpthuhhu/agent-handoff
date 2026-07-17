"""存储后端入口。"""
from __future__ import annotations

from ..config import Settings
from .base import Bundle, BundleMeta, StorageBackend
from .local import LocalStorage


def build_storage(settings: Settings) -> StorageBackend:
    """根据配置构造存储后端。"""
    if settings.storage_backend == "local":
        return LocalStorage(settings.local_storage_dir, settings.local_index_db)
    if settings.storage_backend == "tos":
        from .tos import TosStorage  # 延迟 import,没装 SDK 时不爆

        return TosStorage(
            endpoint=settings.tos_endpoint,
            region=settings.tos_region,
            bucket=settings.tos_bucket,
            access_key=settings.tos_access_key,
            secret_key=settings.tos_secret_key,
            prefix=settings.tos_prefix,
            index_db=settings.local_index_db,  # 复用索引 DB 路径
        )
    raise RuntimeError(f"未知存储后端: {settings.storage_backend}")


__all__ = ["Bundle", "BundleMeta", "StorageBackend", "LocalStorage", "build_storage"]
