"""Multi-layer cache.

Layer 1: in-process TTL cache (``cachetools``) — sub-millisecond, per-worker.
Layer 2: Redis (optional) — shared across workers.

Redis is entirely optional: if ``REDIS_URL`` is empty or unreachable the cache
silently degrades to L1-only mode. This is what makes the app deployable on
Hostinger shared hosting where no Redis is available.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from .config import settings

logger = logging.getLogger("saverfrom.cache")

try:  # cachetools is optional at runtime (plain dict fallback)
    from cachetools import TTLCache
except ImportError:  # pragma: no cover
    TTLCache = None

try:
    import orjson as _json
except ImportError:  # pragma: no cover
    import json as _json


def _dumps(value: Any) -> bytes:
    return _json.dumps(value)


def _loads(raw: bytes) -> Any:
    return _json.loads(raw)


class InMemoryTTLCache:
    """Small thread-safe TTL-aware LRU cache."""

    def __init__(self, maxsize: int = 2000, ttl: int = 300):
        self._cache: Any = TTLCache(maxsize=maxsize, ttl=ttl) if TTLCache else {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            try:
                return self._cache.get(key)
            except Exception:
                return None

    async def set(self, key: str, value: Any) -> None:
        async with self._lock:
            try:
                self._cache[key] = value
            except Exception:
                pass

    async def delete(self, key: str) -> None:
        async with self._lock:
            try:
                self._cache.pop(key, None)
            except Exception:
                pass

    async def clear(self) -> None:
        async with self._lock:
            try:
                self._cache.clear()
            except Exception:
                pass

    @property
    def size(self) -> int:
        try:
            return len(self._cache)
        except Exception:
            return 0


class MultiLayerCache:
    def __init__(
        self,
        redis_url: Optional[str] = None,
        l1_maxsize: int = 2000,
        l1_ttl: int = 300,
        l2_ttl: int = 3600,
    ):
        self._l1 = InMemoryTTLCache(maxsize=l1_maxsize, ttl=l1_ttl)
        self._l2_ttl = l2_ttl
        self._redis = None
        self._redis_url = redis_url or ""
        self._redis_ok = False
        self._stats = {"l1_hits": 0, "l2_hits": 0, "misses": 0, "sets": 0}

    async def connect(self) -> None:
        if not self._redis_url:
            logger.info("MultiLayerCache: Redis URL not configured — L1 only mode")
            return
        try:
            import redis.asyncio as aioredis

            client = aioredis.from_url(
                self._redis_url,
                decode_responses=False,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            await client.ping()
            self._redis = client
            self._redis_ok = True
            logger.info("MultiLayerCache: Redis connected")
        except Exception as exc:
            logger.warning("MultiLayerCache: Redis unavailable (%s) — L1 only mode", exc)
            self._redis_ok = False

    async def disconnect(self) -> None:
        if self._redis:
            try:
                await self._redis.aclose()
            except Exception:
                pass

    async def get(self, key: str):
        """Return ``(value, layer)`` where layer is "L1", "L2" or ``None``."""
        value = await self._l1.get(key)
        if value is not None:
            self._stats["l1_hits"] += 1
            return value, "L1"

        if self._redis_ok:
            try:
                raw = await self._redis.get(key)
                if raw is not None:
                    parsed = _loads(raw)
                    await self._l1.set(key, parsed)
                    self._stats["l2_hits"] += 1
                    return parsed, "L2"
            except Exception as exc:
                logger.warning("Redis GET error: %s", exc)
                self._redis_ok = False

        self._stats["misses"] += 1
        return None, None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        await self._l1.set(key, value)
        if self._redis_ok:
            try:
                await self._redis.setex(key, ttl or self._l2_ttl, _dumps(value))
            except Exception as exc:
                logger.warning("Redis SET error: %s", exc)
                self._redis_ok = False
        self._stats["sets"] += 1

    async def delete(self, key: str) -> None:
        await self._l1.delete(key)
        if self._redis_ok:
            try:
                await self._redis.delete(key)
            except Exception as exc:
                logger.warning("Redis DELETE error: %s", exc)

    async def clear(self) -> None:
        await self._l1.clear()

    def stats(self) -> dict:
        total = self._stats["l1_hits"] + self._stats["l2_hits"] + self._stats["misses"]
        hit_rate = (
            (self._stats["l1_hits"] + self._stats["l2_hits"]) / total * 100 if total else 0.0
        )
        return {
            **self._stats,
            "total_requests": total,
            "hit_rate_pct": round(hit_rate, 2),
            "l1_size": self._l1.size,
            "redis_connected": self._redis_ok,
        }


cache = MultiLayerCache(
    redis_url=settings.REDIS_URL,
    l1_maxsize=settings.CACHE_L1_MAXSIZE,
    l1_ttl=settings.CACHE_L1_TTL,
    l2_ttl=settings.CACHE_L2_TTL,
)


def make_cache_key(*parts: str) -> str:
    return "::".join(str(p or "").strip() for p in parts)