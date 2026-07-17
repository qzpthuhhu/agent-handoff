"""本地文件系统存储后端。

密文存到 `bundles/{id}.bin`(= ciphertext_b64 || nonce_b64 用换行分隔),
元数据走 SQLite 索引。
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .base import Bundle, BundleMeta, StorageBackend


class LocalStorage(StorageBackend):
    name = "local"

    # 密文文件:第一行 ciphertext_b64,第二行 nonce_b64
    # 用换行分隔,足够简单,密文本身是 base64 没有换行

    def __init__(self, storage_dir: Path, index_db: Path):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
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

    def _bin_path(self, bundle_id: str) -> Path:
        return self.storage_dir / f"{bundle_id}.bin"

    def put(self, bundle_id: str, ciphertext_b64: str, nonce_b64: str, hint: Optional[str] = None,
            expires_at: Optional[datetime] = None) -> BundleMeta:
        now = datetime.now(timezone.utc)
        if expires_at is None:
            expires_at = datetime.fromtimestamp(now.timestamp() + 7 * 24 * 3600, tz=timezone.utc)
        size = len(ciphertext_b64.encode("utf-8")) + len(nonce_b64.encode("utf-8")) + 1
        bin_path = self._bin_path(bundle_id)
        with self._lock:
            with open(bin_path, "w", encoding="utf-8") as f:
                f.write(ciphertext_b64)
                f.write("\n")
                f.write(nonce_b64)
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
        bin_path = self._bin_path(bundle_id)
        if not bin_path.exists():
            return None
        with sqlite3.connect(str(self.index_db)) as conn:
            row = conn.execute(
                "SELECT size, created_at, expires_at, consumed, hint FROM bundles WHERE id=?",
                (bundle_id,),
            ).fetchone()
        if not row:
            return None
        size, created_at, expires_at, consumed, hint = row
        with open(bin_path, "r", encoding="utf-8") as f:
            content = f.read()
        parts = content.split("\n", 1)
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
        bin_path = self._bin_path(bundle_id)
        deleted = False
        with self._lock:
            if bin_path.exists():
                bin_path.unlink()
                deleted = True
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
