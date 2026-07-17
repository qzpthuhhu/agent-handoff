"""后台清理任务:定期删除过期 bundle。

启停方式:
- 应用启动时由 lifespan 拉起
- 关闭时随 lifespan 退出
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from .storage import StorageBackend

logger = logging.getLogger(__name__)


class CleanupTask:
    def __init__(self, storage: StorageBackend, interval: int):
        self.storage = storage
        self.interval = interval
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="agent-handoff-cleanup")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()

    async def _run(self) -> None:
        logger.info("cleanup task started, interval=%ds", self.interval)
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception:
                logger.exception("cleanup tick failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval)
            except asyncio.TimeoutError:
                continue
        logger.info("cleanup task stopped")

    def _tick(self) -> None:
        now = datetime.now(timezone.utc)
        expired = self.storage.list_expired(now)
        if not expired:
            return
        logger.info("cleaning %d expired bundles", len(expired))
        for meta in expired:
            try:
                self.storage.delete(meta.id)
                logger.debug("deleted expired bundle %s", meta.id)
            except Exception:
                logger.exception("delete failed for %s", meta.id)
