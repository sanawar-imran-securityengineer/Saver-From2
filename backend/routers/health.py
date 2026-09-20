"""Health, stats and registry endpoints.

Exposes the same paths the original gateway used (``/api/v1/health``) plus the
conventional ``/api/health`` so uptime monitors and Hostinger's health checks
both work.
"""

from __future__ import annotations

import time
from typing import Any, Dict

from fastapi import APIRouter

from ..services.downloader import ffmpeg_available
from ..utils.cache import cache
from ..utils.circuit_breaker import circuit_breakers
from ..utils.config import settings
from ..utils.cleanup import FileCleanupService
from ..utils.platforms import PLATFORMS

router = APIRouter(tags=["Health"])

START_TIME = time.time()

# Shared cleanup service reference (set by main.py so /stats can report it).
_cleanup_service: FileCleanupService | None = None


def register_cleanup_service(service: FileCleanupService) -> None:
    global _cleanup_service
    _cleanup_service = service


def _platform_blocks() -> Dict[str, Any]:
    blocks: Dict[str, Any] = {}
    for spec in PLATFORMS:
        breaker = circuit_breakers.get(spec.key)
        blocks[spec.key] = {
            "platform": spec.key,
            "name": spec.name,
            "status": "MAINTENANCE" if (breaker and breaker.is_open) else "ONLINE",
            "formats": list(spec.formats),
            "page": f"/pages/{spec.page}",
        }
    return blocks


def _health_payload() -> Dict[str, Any]:
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "uptime_seconds": round(time.time() - START_TIME, 2),
        "ffmpeg_available": ffmpeg_available(),
        "redis_connected": cache.stats()["redis_connected"],
        "downloads_dir": str(settings.DOWNLOADS_DIR),
        "platform_count": len(PLATFORMS),
        "platforms": _platform_blocks(),
    }


@router.get("/api/health")
async def health() -> Dict[str, Any]:
    return _health_payload()


@router.get("/api/v1/health")
async def health_v1() -> Dict[str, Any]:
    """Backwards-compatible alias used by the original gateway."""
    return _health_payload()


@router.get("/api/v1/stats")
@router.get("/api/stats")
async def stats() -> Dict[str, Any]:
    payload = {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "uptime_seconds": round(time.time() - START_TIME, 2),
        "cache": cache.stats(),
        "circuit_breakers": [cb.snapshot() for cb in circuit_breakers.values()],
        "config": {
            "max_file_size_mb": settings.MAX_FILE_SIZE_MB,
            "download_timeout_seconds": settings.DOWNLOAD_TIMEOUT_SECONDS,
            "file_ttl_minutes": settings.FILE_TTL_MINUTES,
            "max_concurrent_downloads": settings.MAX_CONCURRENT_DOWNLOADS,
            "rate_limit_per_minute": settings.RATE_LIMIT_PER_MINUTE,
            "metadata_cache_ttl": settings.METADATA_CACHE_TTL,
        },
    }
    if _cleanup_service is not None:
        payload["cleanup"] = {
            "ttl_seconds": _cleanup_service.ttl_seconds,
            "interval_seconds": _cleanup_service.interval,
            "removed_total": _cleanup_service.removed_total,
        }
    return payload


@router.get("/api/v1/info")
async def info() -> Dict[str, Any]:
    """Short machine-readable summary of what this deployment supports."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "platforms": [spec.key for spec in PLATFORMS],
        "routes": [f"/api/{spec.key}" for spec in PLATFORMS],
        "frontend_routes": ["/"] + [f"/{spec.key}" for spec in PLATFORMS],
        "server_side_download": True,
        "requires_api_keys": False,
    }