"""Unified endpoints — the contract the existing frontend already calls.

* ``POST /api/v1/detect``          – identify the platform for a URL
* ``POST /api/v1/download``        – metadata + real direct stream URL
* ``POST /api/v1/download-file``   – real server-side download (any platform)
* ``GET  /api/v1/proxy-download``  – stream a remote URL to the browser as an
  attachment, working around cross-origin download restrictions
* ``GET  /api/v1/platforms``       – the registry the UI renders from

The response shape is unchanged from the original gateway so
``frontend/pages/*.html`` keeps working as-is.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, StreamingResponse

from ..services import resolver
from ..services.downloader import DownloadError, downloader_manager
from ..utils.config import settings
from ..utils.circuit_breaker import get_breaker
from ..utils.detector import detect_platform
from ..utils.models import DetectRequest, DownloadRequest, ErrorResponse
from ..utils.platforms import PLATFORMS, get_platform
from ..utils.ratelimit import rate_limit
from ..utils.security import safe_download_name, sanitize_url
from ..utils.validators import validate_url

logger = logging.getLogger("saverfrom.unified")

router = APIRouter(tags=["Unified"])

# Headers used when proxying a remote stream.
_PROXY_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
}


def _registry_payload() -> list:
    return [
        {
            "key": spec.key,
            "name": spec.name,
            "icon": spec.icon,
            "accent_color": spec.accent_color,
            "page": f"/pages/{spec.page}",
            "route": f"/{spec.key}",
            "formats": list(spec.formats),
            "options": [{"value": v, "label": l} for v, l in spec.option_pairs],
            "sample_url": spec.sample_url,
            "needs_ffmpeg": spec.needs_ffmpeg,
        }
        for spec in PLATFORMS
    ]


@router.get("/api/v1/platforms")
@router.get("/api/platforms")
async def list_platforms() -> Dict[str, Any]:
    """Everything the frontend needs to render the platform grid."""
    return {"success": True, "count": len(PLATFORMS), "platforms": _registry_payload()}


@router.post("/api/v1/detect")
async def detect(request: Request) -> Dict[str, Any]:
    """Identify which platform a URL belongs to."""
    try:
        payload = await request.json()
    except Exception:
        return ErrorResponse(error="invalid_body", message="A JSON body is required.").model_dump()

    url = (payload or {}).get("url", "") if isinstance(payload, dict) else ""
    url = (url or "").strip()
    if not url:
        return ErrorResponse(error="empty_url", message="URL cannot be empty.").model_dump()

    platform_enum, error = detect_platform(url)
    if error:
        return ErrorResponse(error="detect_error", message=error).model_dump()

    spec = get_platform(platform_enum.value)
    return {
        "success": True,
        "platform": spec.key,
        "platform_name": spec.name,
        "icon": spec.icon,
        "accent_color": spec.accent_color,
        "page": f"/pages/{spec.page}",
        "formats": list(spec.formats),
        "url": url,
    }


@router.post("/api/v1/download")
async def unified_download(payload: DownloadRequest = Body(...)) -> Dict[str, Any]:
    """Resolve real metadata + a direct download URL for any supported link."""
    is_valid, error = validate_url(payload.url)
    if not is_valid:
        return ErrorResponse(error="validation_error", message=error or "Invalid URL.").model_dump()

    platform_enum, detect_error = detect_platform(payload.url)
    if detect_error:
        return ErrorResponse(error="detect_error", message=detect_error).model_dump()

    spec = get_platform(platform_enum.value)
    breaker = get_breaker(spec.key)
    if breaker.is_open:
        return ErrorResponse(
            error="maintenance",
            message=f"{spec.name} is temporarily unavailable for maintenance.",
            platform=spec.key,
        ).model_dump()

    requested = (payload.format or payload.option or payload.quality or "best").strip().lower()
    if requested not in spec.formats:
        requested = "best" if "best" in spec.formats else spec.formats[0]

    try:
        result = await resolver.resolve_metadata(payload.url.strip(), requested, spec)
        breaker.record_success()
        result["source_url"] = payload.url.strip()
        return result
    except LookupError as exc:
        breaker.record_failure()
        return ErrorResponse(
            error="extract_failed", message=str(exc), platform=spec.key
        ).model_dump()
    except Exception as exc:
        breaker.record_failure()
        logger.exception("Unified download failed")
        return ErrorResponse(
            error="server_error", message=f"Unexpected error: {exc}", platform=spec.key
        ).model_dump()


@router.post("/api/v1/download-file", dependencies=[Depends(rate_limit("unified-file"))])
async def unified_download_file(payload: DownloadRequest = Body(...)) -> Dict[str, Any]:
    """Real server-side download for any supported platform.

    Writes the file to disk and returns a local file URL, which is what makes
    downloads reliable for platforms whose CDN links expire or block browsers.
    """
    is_valid, error = validate_url(payload.url)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)

    platform_enum, detect_error = detect_platform(payload.url)
    if detect_error:
        raise HTTPException(status_code=400, detail=detect_error)

    spec = get_platform(platform_enum.value)
    requested = (payload.format or payload.option or payload.quality or "best").strip().lower()
    if requested not in spec.formats:
        requested = "best" if "best" in spec.formats else spec.formats[0]

    try:
        result = await downloader_manager.download(
            payload.url.strip(), settings.DOWNLOADS_DIR, requested, spec
        )
    except DownloadError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "success": True,
        "platform": spec.key,
        "platform_name": spec.name,
        "title": result.title,
        "filename": result.filename,
        "quality": result.quality_selected,
        "quality_selected": result.quality_selected,
        "option_requested": result.option_requested,
        "downloader_used": result.downloader_used,
        "download_url": f"/api/file/{result.filename}",
        "file_url": f"/api/file/{result.filename}",
        "file_size": result.file_size,
        "thumbnail": result.thumbnail,
        "duration": result.duration,
    }


@router.get("/api/v1/proxy-download")
async def proxy_download(url: str, filename: Optional[str] = None) -> Any:
    """Stream a remote media URL to the browser as an attachment.

    This is what lets the frontend offer a real "Download" button for direct
    CDN links that would otherwise open in a new tab instead of saving.
    """
    if not url or not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="A valid absolute URL is required.")

    if "youtube.com/" in url or "youtu.be/" in url:
        raise HTTPException(
            status_code=400,
            detail="YouTube files must be downloaded through the server download button.",
        )

    safe_name = safe_download_name(
        (filename or "media").rsplit(".", 1)[0], (filename or "media.mp4").rsplit(".", 1)[-1]
    )
    content_type = "audio/mpeg" if safe_name.endswith(".mp3") else "video/mp4"

    headers = dict(_PROXY_HEADERS)
    if "googlevideo.com" in url:
        headers["Referer"] = "https://www.youtube.com/"
        headers["Origin"] = "https://www.youtube.com/"
    elif "cdninstagram.com" in url or "fbcdn.net" in url:
        headers["Referer"] = "https://www.instagram.com/"
        headers["Origin"] = "https://www.instagram.com/"

    client = httpx.AsyncClient(timeout=60.0, follow_redirects=True)
    try:
        request = client.build_request("GET", url, headers=headers)
        upstream = await client.send(request, stream=True)
    except Exception as exc:
        await client.aclose()
        logger.info("Proxy stream failed, redirecting instead: %s", exc)
        return RedirectResponse(url=url)

    if upstream.status_code >= 400:
        await upstream.aclose()
        await client.aclose()
        # Let the browser try the source URL directly.
        return RedirectResponse(url=url)

    async def stream_body():
        try:
            async for chunk in upstream.aiter_bytes(chunk_size=4194304):  # 4 MB chunks
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    import urllib.parse
    encoded_name = urllib.parse.quote(safe_name)
    return StreamingResponse(
        stream_body(),
        media_type=content_type,
        headers={
            "Content-Disposition": f"attachment; filename*=utf-8''{encoded_name}",
            "Cache-Control": "no-store",
        },
    )