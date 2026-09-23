"""Shared router factory — all 10 platform routers are built from this.

Each ``backend/routers/<platform>.py`` module calls
:func:`build_platform_router` with its own :class:`PlatformSpec`, so every
platform gets an identical, fully-featured API surface while the per-platform
files stay tiny and readable.

Endpoints created per platform (``<key>`` = youtube, tiktok, ...):

* ``GET  /api/<key>/health``            – liveness + ffmpeg availability
* ``GET  /api/<key>/formats``           – the option pills for the UI
* ``GET  /api/<key>/info?url=``         – metadata + real direct stream URL
* ``POST /api/<key>/download``          – REAL server-side download to disk
* ``POST /api/<key>/resolve``           – unified resolver (metadata/direct URL)
* ``GET  /api/<key>/file/<filename>``   – serve a downloaded file
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse

from ..services import resolver
from ..services.downloader import DownloadError, downloader_manager, ffmpeg_available
from ..utils.config import settings
from ..utils.models import DownloadRequest, ErrorResponse, PlatformEnum
from ..utils.platforms import PlatformSpec, platform_keys
from ..utils.ratelimit import rate_limit
from ..utils.security import resolve_safe_path, secure_log
from ..utils.validators import validate_url


def _require_platform(url: str, spec: PlatformSpec) -> str:
    """Validate the URL and make sure it really belongs to ``spec``."""
    is_valid, error = validate_url(url)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)
    if not spec.regex.search(url.strip()):
        raise HTTPException(
            status_code=400,
            detail=(
                f"This link does not look like a {spec.name} URL. "
                "Use a valid link from the platform, or the all-in-one downloader."
            ),
        )
    return url.strip()


def _requested_option(payload: DownloadRequest, spec: PlatformSpec) -> str:
    """Resolve the effective option, defaulting to the first allowed one."""
    candidate = (
        payload.format_id or payload.format or payload.quality or payload.option or "best"
    ).strip().lower()
    if candidate in spec.formats:
        return candidate
    if "best" in spec.formats:
        return "best"
    return spec.formats[0]


def build_platform_router(spec: PlatformSpec) -> APIRouter:
    """Create the API router for a single platform."""
    router = APIRouter(prefix=f"/api/{spec.key}", tags=[spec.name])

    @router.get("/health")
    async def platform_health() -> Dict[str, Any]:
        return {
            "status": "ok",
            "platform": spec.key,
            "name": spec.name,
            "formats": list(spec.formats),
            "ffmpeg_available": ffmpeg_available(),
            "server_side_download": True,
        }

    @router.get("/formats")
    async def platform_formats() -> Dict[str, Any]:
        return {
            "platform": spec.key,
            "name": spec.name,
            "accent_color": spec.accent_color,
            "icon": spec.icon,
            "page": f"/pages/{spec.page}",
            "sample_url": spec.sample_url,
            "formats": list(spec.formats),
            "options": [
                {"value": value, "label": label} for value, label in spec.option_pairs
            ],
            "needs_ffmpeg": spec.needs_ffmpeg,
        }

    @router.get("/info")
    async def platform_info(
        url: str = Query(..., description=f"{spec.name} media URL"),
        option: str = Query("best", description="Requested format"),
    ) -> Dict[str, Any]:
        """Return real metadata plus a direct, playable stream URL."""
        _require_platform(url, spec)
        requested = option.strip().lower() if option else "best"
        if requested not in spec.formats:
            requested = "best" if "best" in spec.formats else spec.formats[0]
        try:
            return await resolver.resolve_metadata(url.strip(), requested, spec)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/resolve", dependencies=[Depends(rate_limit(f"{spec.key}-resolve"))])
    async def platform_resolve(payload: DownloadRequest = Body(...)) -> Dict[str, Any]:
        """Same as ``/info`` but POST + body, mirroring the legacy contract."""
        try:
            _require_platform(payload.url, spec)
        except HTTPException as exc:
            return ErrorResponse(
                error="validation_error", message=str(exc.detail), platform=spec.key
            ).model_dump()
        requested = _requested_option(payload, spec)
        try:
            return await resolver.resolve_metadata(payload.url.strip(), requested, spec)
        except LookupError as exc:
            return ErrorResponse(
                error="extract_failed", message=str(exc), platform=spec.key
            ).model_dump()

    @router.post("/download", dependencies=[Depends(rate_limit(f"{spec.key}-download"))])
    async def platform_download(payload: DownloadRequest = Body(...)) -> Dict[str, Any]:
        """Really download the media to the server and return a file URL.

        This is the behaviour of the original per-platform services: the file is
        written into ``DOWNLOADS_DIR`` under a UUID name and served back by
        ``/api/<platform>/file/<name>`` (and the shared ``/api/file/<name>``).
        """
        _require_platform(payload.url, spec)
        requested = _requested_option(payload, spec)
        if requested == "mp3" and not ffmpeg_available():
            raise HTTPException(
                status_code=503,
                detail=(
                    "MP3 conversion needs ffmpeg on the server. Install ffmpeg or set "
                    "FFMPEG_LOCATION, or choose an MP4 format instead."
                ),
            )
        secure_log("download requested", payload.url, platform=spec.key, option=requested)
        try:
            result = await downloader_manager.download(
                payload.url.strip(), settings.DOWNLOADS_DIR, requested, spec
            )
        except DownloadError as exc:
            err_msg = str(exc)
            # Provide friendlier messages for the most common failure modes.
            if "corrupted" in err_msg.lower() or "not contain a valid video" in err_msg.lower():
                detail = (
                    f"The downloaded file from {spec.name} appears corrupted. "
                    "This usually means the CDN link expired. Please paste the URL again and retry."
                )
            elif "audio track is missing" in err_msg.lower():
                detail = (
                    f"Video downloaded successfully but the audio track is missing. "
                    "FFmpeg is merging the streams — please try once more."
                )
            elif "timed out" in err_msg.lower() or "timeout" in err_msg.lower():
                detail = (
                    f"The {spec.name} server took too long to respond. "
                    "Please try again in a moment."
                )
            elif "failed after" in err_msg.lower():
                detail = (
                    f"Could not download from {spec.name} after multiple attempts. "
                    f"The post may be private, deleted, or temporarily unavailable. ({err_msg})"
                )
            else:
                detail = err_msg
            raise HTTPException(status_code=502, detail=detail) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Download failed: {exc}") from exc

        secure_log(
            "download completed",
            payload.url,
            platform=spec.key,
            filename=result.filename,
            size=result.file_size,
        )
        return {
            "success": True,
            "platform": spec.key,
            "platform_name": spec.name,
            "title": result.title,
            "filename": result.filename,
            "option_requested": result.option_requested,
            "quality_selected": result.quality_selected,
            "quality": result.quality_selected,
            "downloader_used": result.downloader_used,
            "download_url": f"/api/{spec.key}/file/{result.filename}",
            "file_url": f"/api/file/{result.filename}",
            "file_size": result.file_size,
            "thumbnail": result.thumbnail,
            "duration": result.duration,
            "format": "MP3 Audio" if requested == "mp3" else "MP4 Video",
        }

    @router.get("/file/{filename}")
    async def platform_file(filename: str) -> FileResponse:
        """Serve a previously downloaded file (UUID names only)."""
        safe_path: Path | None = resolve_safe_path(filename, settings.DOWNLOADS_DIR)
        if safe_path is None or not safe_path.exists():
            raise HTTPException(status_code=404, detail="File not found or expired.")
        media_type = "audio/mpeg" if safe_path.suffix.lower() == ".mp3" else "video/mp4"
        return FileResponse(
            path=str(safe_path),
            media_type=media_type,
            filename=safe_path.name,
            headers={
                "Cache-Control": "public, max-age=1800",
                "Content-Disposition": f'attachment; filename="{safe_path.name}"',
            },
        )

    return router


def build_all_platform_routers() -> List[APIRouter]:
    """Build every platform router from the registry."""
    from ..utils.platforms import PLATFORMS

    return [build_platform_router(spec) for spec in PLATFORMS]


__all__ = [
    "build_platform_router",
    "build_all_platform_routers",
    "platform_keys",
    "PlatformEnum",
]