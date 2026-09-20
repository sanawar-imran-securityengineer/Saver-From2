"""Background task that deletes downloaded files after their TTL expires."""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from .config import settings

logger = logging.getLogger("saverfrom.cleanup")


class FileCleanupService:
    """Periodically removes files in ``downloads_dir`` older than the TTL.

    Runs in a background asyncio task; every cycle errors are swallowed so a
    single bad file can never kill the service.
    """

    def __init__(self, downloads_dir: Path, ttl_minutes: int | None = None, interval: int | None = None):
        self.downloads_dir = Path(downloads_dir)
        self.ttl_seconds = (ttl_minutes if ttl_minutes is not None else settings.FILE_TTL_MINUTES) * 60
        self.interval = interval or settings.CLEANUP_INTERVAL_SECONDS
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()
        self.removed_total = 0

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stopping.clear()
        self._task = asyncio.create_task(self._loop(), name="file-cleanup")
        logger.info("FileCleanupService started (ttl=%ss interval=%ss)", self.ttl_seconds, self.interval)

    async def stop(self) -> None:
        self._stopping.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        logger.info("FileCleanupService stopped")

    async def _loop(self) -> None:
        while not self._stopping.is_set():
            try:
                await asyncio.sleep(self.interval)
                self.sweep()
            except asyncio.CancelledError:
                break
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Cleanup cycle failed: %s", exc)

    def sweep(self) -> int:
        """Delete expired files now. Returns the number of files removed."""
        if not self.downloads_dir.exists():
            return 0
        cutoff = time.time() - self.ttl_seconds
        removed = 0
        for entry in self.downloads_dir.iterdir():
            try:
                if not entry.is_file():
                    continue
                if entry.stat().st_mtime < cutoff:
                    entry.unlink()
                    removed += 1
            except Exception:
                continue
        self.removed_total += removed
        if removed:
            logger.info("Cleanup removed %s expired file(s)", removed)
        return removed