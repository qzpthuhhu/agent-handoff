"""火山引擎 TOS 存储后端。

依赖:`pip install -r requirements-tos.txt`(包名 `tos`)。

密文存到 `{prefix}/{id}.bin`,内容是 `ciphertext_b64 + "\\n" + nonce_b64`。
元数据走 SQLite 索引(单独路径 `.tos-index.sqlite`,跟 local 不冲突)。
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .base import Bundle, BundleMeta, StorageBackend

try:
    import tos  # type: ignore
    from tos import TosClientV2  # type: ignore
except Exception as e:  # pragma: no cover - 依赖缺失时给清晰报错
    tos = None  # type: ignore
    TosClientV2 = None  # type: ignore
    _IMPORT_ERROR: Optional[Exception] = e
else:
    _IMPORT_ERROR = None


class TosStorage(StorageBackend):
    name = "tos"

    def __init__(
        self,
        endpoint: str,
        region: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        prefix: str = "bundles",
        index_db: Optional[Path] = None,
    ):
        if _IMPORT_ERROR is not None:
            raise RuntimeError(
                "未安装 tos SDK,请先执行: pip install -r requirements-tos.txt"
            ) from _IMPORT_ERROR
        if not access_key or not secret_key:
            raise RuntimeError("TOS 模式必须配置 TOS_ACCESS_KEY 和 TOS_SECRET_KEY")

        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.client = TosClientV2(
            ak=access_key,
            sk=secret_key,
            endpoint=endpoint,
            region=region,
        )
        # 元数据走本地 SQLite(不依赖对象存储的元数据查询)
        if index_db is None:
            index_db = Path.home() / ".agent-handoff" / "tos-index.sqlite"
        self.index_db = Path(index_db)
        self.index_db.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(str(self.index_db)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bundles (
                    id TEXT PRIMARY KEY,
                    size INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    consumed INTEGER NOT NULL DEFAULT 0,
                    hint TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_expires ON bundles(expires_at)")
            conn.commit()

    def _object_key(self, bundle_id: str) -> str:
        return f"{self.prefix}/{bundle_id}.bin"

    def put(self, bundle_id: str, ciphertext_b64: str, nonce_b64: str, hint: Optional[str] = None,
            expires_at: Optional[datetime] = None) -> BundleMeta:
        now = datetime.now(timezone.utc)
        if expires_at is None:
            expires_at = datetime.fromtimestamp(now.timestamp() + 7 * 24 * 3600, tz=timezone.utc)
        body = (ciphertext_b64 + "\n" + nonce_b64).encode("utf-8")
        size = len(body)
        key = self._object_key(bundle_id)
        # TOS 自定义元数据(可选)
        custom = {
            "x-handoff-hint": (hint or "")[:200],
            "x-handoff-expires-at": expires_at.isoformat(),
        }
        self.client.put_object(bucket=self.bucket, key=key, content=body, headers=custom)
        with self._lock:
            with sqlite3.connect(str(self.index_db)) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO bundles(id, size, created_at, expires_at, consumed, hint)
                    VALUES(?, ?, ?, ?, 0, ?)
                    """,
                    (bundle_id, size, now.isoformat(), expires_at.isoformat(), hint),
                )
                conn.commit()
        return BundleMeta(
            id=bundle_id, size=size, created_at=now, expires_at=expires_at, hint=hint
        )

    def get(self, bundle_id: str) -> Optional[Bundle]:
        with sqlite3.connect(str(self.index_db)) as conn:
            row = conn.execute(
                "SELECT size, created_at, expires_at, consumed, hint FROM bundles WHERE id=?",
                (bundle_id,),
            ).fetchone()
        if not row:
            return None
        size, created_at, expires_at, consumed, hint = row
        try:
            result = self.client.get_object(bucket=self.bucket, key=self._object_key(bundle_id))
            body = b"".join(result.content.iter_chunks())
        except Exception:
            return None
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError:
            return None
        parts = text.split("\n", 1)
        if len(parts) != 2:
            return None
        ciphertext_b64, nonce_b64 = parts
        return Bundle(
            id=bundle_id,
            size=size,
            ciphertext_b64=ciphertext_b64,
            nonce_b64=nonce_b64,
            hint=hint,
            expires_at=datetime.fromisoformat(expires_at),
            consumed=bool(consumed),
            created_at=datetime.fromisoformat(created_at),
        )

    def delete(self, bundle_id: str) -> bool:
        deleted = False
        with self._lock:
            try:
                self.client.delete_object(bucket=self.bucket, key=self._object_key(bundle_id))
                deleted = True
            except Exception:
                pass
            with sqlite3.connect(str(self.index_db)) as conn:
                cur = conn.execute("DELETE FROM bundles WHERE id=?", (bundle_id,))
                conn.commit()
                if cur.rowcount > 0:
                    deleted = True
        return deleted

    def list_expired(self, now: datetime) -> list[BundleMeta]:
        with sqlite3.connect(str(self.index_db)) as conn:
            rows = conn.execute(
                "SELECT id, size, created_at, expires_at, consumed, hint FROM bundles WHERE expires_at < ?",
                (now.isoformat(),),
            ).fetchall()
        out: list[BundleMeta] = []
        for row in rows:
            id_, size, created_at, expires_at, _consumed, hint = row
            out.append(
                BundleMeta(
                    id=id_,
                    size=size,
                    created_at=datetime.fromisoformat(created_at),
                    expires_at=datetime.fromisoformat(expires_at),
                    hint=hint,
                )
            )
        return out

    def mark_consumed(self, bundle_id: str) -> bool:
        with self._lock:
            with sqlite3.connect(str(self.index_db)) as conn:
                cur = conn.execute(
                    "UPDATE bundles SET consumed=1 WHERE id=? AND consumed=0", (bundle_id,)
                )
                conn.commit()
                return cur.rowcount > 0
