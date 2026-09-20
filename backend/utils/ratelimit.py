"""Tiny in-process rate limiter (no external dependency).

The original services used ``slowapi``. That works, but it adds another
dependency and decorates every route. Because a single Hostinger process serves
this app, a small sliding-window counter is enough and keeps the deployment
surface minimal.

Per-IP, per-route-bucket. Configured by ``RATE_LIMIT_PER_MINUTE``
(0 disables limiting entirely).
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import HTTPException, Request

from .config import settings


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: int = 60):
        self.limit = limit
        self.window = window_seconds
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        if self.limit <= 0:
            return
        now = time.monotonic()
        bucket = self._hits[key]
        while bucket and (now - bucket[0]) > self.window:
            bucket.popleft()
        if len(bucket) >= self.limit:
            retry_after = int(self.window - (now - bucket[0])) + 1
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please slow down and try again shortly.",
                headers={"Retry-After": str(retry_after)},
            )
        bucket.append(now)

    def reset(self) -> None:
        self._hits.clear()

    @property
    def tracked_keys(self) -> int:
        return len(self._hits)


limiter = SlidingWindowLimiter(settings.RATE_LIMIT_PER_MINUTE)


def client_ip(request: Request) -> str:
    """Best-effort client IP, honouring the proxy headers Hostinger sets."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


def rate_limit(bucket: str = "default"):
    """FastAPI dependency factory: ``Depends(rate_limit("youtube"))``."""

    async def _dependency(request: Request) -> None:
        limiter.check(f"{bucket}:{client_ip(request)}")

    return _dependency