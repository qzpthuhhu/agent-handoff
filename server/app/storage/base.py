"""存储后端抽象。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Bundle:
    """从存储中读出的 bundle 摘要。"""

    id: str
    size: int
    ciphertext_b64: str
    nonce_b64: str
    hint: Optional[str] = None
    expires_at: Optional[datetime] = None
    consumed: bool = False
    created_at: Optional[datetime] = None


@dataclass
class BundleMeta:
    """bundle 元数据(不含密文,用于索引/管理)。"""

    id: str
    size: int
    created_at: datetime
    expires_at: datetime
    consumed: bool = False
    hint: Optional[str] = None


class StorageBackend(ABC):
    """所有存储后端必须实现的接口。"""

    name: str = "base"

    @abstractmethod
    def put(self, bundle_id: str, ciphertext_b64: str, nonce_b64: str, hint: Optional[str] = None,
            expires_at: Optional[datetime] = None) -> BundleMeta:
        """存储密文 + 元数据,返回 BundleMeta。"""

    @abstractmethod
    def get(self, bundle_id: str) -> Optional[Bundle]:
        """读 bundle,不存在返回 None。"""

    @abstractmethod
    def delete(self, bundle_id: str) -> bool:
        """删除 bundle,返回是否真的删了。"""

    @abstractmethod
    def list_expired(self, now: datetime) -> list[BundleMeta]:
        """列出已过期的 bundle 元数据。"""

    @abstractmethod
    def mark_consumed(self, bundle_id: str) -> bool:
        """标记一次性消费,返回是否真的标记了。"""
