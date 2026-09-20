"""Admin / maintenance endpoints.

Preserved from the original gateway's ``/api/v1/admin/maintenance`` so platform
outages can be handled without a redeploy.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException

from ..utils.cache import cache
from ..utils.circuit_breaker import circuit_breakers, get_breaker
from ..utils.config import settings
from ..utils.platforms import PLATFORMS_BY_KEY
from ..utils.ratelimit import limiter

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


@router.post("/maintenance")
async def set_maintenance(toggle: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Force a platform into (or out of) maintenance mode."""
    platform = toggle.get("platform")
    enabled = bool(toggle.get("enabled", False))
    reason = toggle.get("reason", "Scheduled maintenance")

    if platform not in PLATFORMS_BY_KEY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown platform '{platform}'. Valid: {sorted(PLATFORMS_BY_KEY)}",
        )

    breaker = get_breaker(platform)
    if enabled:
        breaker.force_open(reason)
    else:
        breaker.force_close()

    return {
        "success": True,
        "platform": platform,
        "maintenance": enabled,
        "reason": reason if enabled else None,
        "state": breaker.state,
    }


@router.get("/circuit-breakers")
async def list_breakers() -> Dict[str, Any]:
    return {
        "success": True,
        "circuit_breakers": [cb.snapshot() for cb in circuit_breakers.values()],
    }


@router.post("/cache/clear")
async def clear_cache() -> Dict[str, Any]:
    await cache.clear()
    return {"success": True, "message": "In-process cache cleared."}


@router.post("/rate-limit/reset")
async def reset_rate_limit() -> Dict[str, Any]:
    limiter.reset()
    return {"success": True, "message": "Rate limiter counters reset."}


@router.get("/settings")
async def current_settings() -> Dict[str, Any]:
    """Read-only view of the effective configuration (never leaks secrets)."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG,
        "downloads_dir": str(settings.DOWNLOADS_DIR),
        "max_file_size_mb": settings.MAX_FILE_SIZE_MB,
        "download_timeout_seconds": settings.DOWNLOAD_TIMEOUT_SECONDS,
        "file_ttl_minutes": settings.FILE_TTL_MINUTES,
        "max_concurrent_downloads": settings.MAX_CONCURRENT_DOWNLOADS,
        "max_retries": settings.MAX_RETRIES,
        "rate_limit_per_minute": settings.RATE_LIMIT_PER_MINUTE,
        "cors_origins": settings.cors_origins_list,
        "allowed_hosts": settings.allowed_hosts_list,
        "redis_configured": bool(settings.REDIS_URL),
        "ffmpeg_location": settings.FFMPEG_LOCATION or None,
    }