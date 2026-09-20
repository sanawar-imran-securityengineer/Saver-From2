"""AsyncSingleFlight — prevents duplicate concurrent yt-dlp extractions.

When many users request the same URL while an extraction is already running,
only ONE extraction runs; all other callers await the shared result.

Preserved verbatim (logic-wise) from the original services.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Tuple

logger = logging.getLogger("saverfrom.single_flight")


class AsyncSingleFlight:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._inflight: Dict[str, Tuple[asyncio.Event, list]] = {}

    async def do(self, key: str, coro_factory) -> Any:
        """Run ``coro_factory()`` once per in-flight ``key``."""
        async with self._lock:
            if key in self._inflight:
                event, holder = self._inflight[key]
                is_caller = False
            else:
                event = asyncio.Event()
                holder: list = []
                self._inflight[key] = (event, holder)
                is_caller = True

        if not is_caller:
            logger.debug("SingleFlight: waiting on in-flight key=%s", key[:80])
            await event.wait()
            if len(holder) == 2 and holder[0] is None:
                raise holder[1]
            return holder[0]

        try:
            logger.debug("SingleFlight: executing key=%s", key[:80])
            result = await coro_factory()
            holder.append(result)
            return result
        except Exception as exc:
            holder.append(None)
            holder.append(exc)
            raise
        finally:
            async with self._lock:
                self._inflight.pop(key, None)
            event.set()

    @property
    def inflight_count(self) -> int:
        return len(self._inflight)


# Shared deduplicators used by the routers.
single_flight_info = AsyncSingleFlight()
single_flight_download = AsyncSingleFlight()