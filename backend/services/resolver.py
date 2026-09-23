"""Unified media resolver.

Implements the same three-step strategy the original gateway used, but with the
**fake sample-media fallbacks removed** (per the project requirements):

1. Platform fast path   — TikTok via the public tikwm API.
2. yt-dlp metadata      — real direct stream URL for every supported platform.
3. OpenGraph scrape     — real title + thumbnail when yt-dlp is blocked.

When every strategy fails the resolver reports a clear error instead of
returning a placeholder video, so the UI can tell the user the truth.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from ..utils.cache import cache, make_cache_key
from ..utils.config import settings
from ..utils.platforms import PlatformSpec
from ..utils.security import safe_download_name
from ..utils.single_flight import single_flight_info
from . import extractors
from .ytdlp import extract_media_with_ytdlp, pick_stream_url

logger = logging.getLogger("saverfrom.resolver")


def _quality_label(requested: str) -> str:
    if requested == "mp3":
        return "Audio 192kbps"
    if requested in ("2160p", "4k"):
        return "4K UHD"
    if requested == "1440p":
        return "1440p QHD"
    if requested == "1080p":
        return "1080p Full HD"
    if requested == "720p":
        return "720p HD"
    if requested == "360p":
        return "360p SD"
    return "Best available"


def _format_payload(url: str, requested: str, spec: PlatformSpec) -> list:
    """Build the ``formats`` array the frontend renders."""
    items = []
    for value, label in spec.option_pairs:
        items.append(
            {
                "format_id": value,
                "quality": label,
                "ext": "mp3" if value == "mp3" else "mp4",
                # Only the requested format has a verified URL; the other pills
                # point at the same resolved stream so they stay usable.
                "url": url,
                "is_selected": value == requested,
            }
        )
    return items


def _duration_str(duration) -> str | None:
    if not duration:
        return None
    try:
        return f"{int(duration // 60):02d}:{int(duration % 60):02d}"
    except (TypeError, ValueError):
        return None


def _tiktok_result(data: Dict[str, Any], requested: str, spec: PlatformSpec) -> Dict[str, Any]:
    chosen = data["audio_url"] if requested == "mp3" else data["download_url"]
    ext = "mp3" if requested == "mp3" else "mp4"
    return {
        "success": True,
        "platform": spec.key,
        "platform_name": spec.name,
        "title": data["title"],
        "thumbnail": data.get("thumbnail"),
        "duration": data.get("duration"),
        "uploader": data.get("uploader", ""),
        "download_url": chosen,
        "url": chosen,
        "stream_url": chosen,
        "filename": safe_download_name(data["title"], ext, "tiktok_video"),
        "quality": _quality_label(requested),
        "format": "MP3 Audio" if ext == "mp3" else "MP4 Video",
        "extension": ext,
        "formats": _format_payload(chosen, requested, spec),
        "extractor": "tikwm",
        # TikTok CDN URLs time out when streamed through the proxy endpoint.
        # The frontend should use the server-side /download endpoint instead.
        "server_download_required": True,
    }


def _ytdlp_result(
    info: Dict[str, Any], stream_url: str, url: str, requested: str, spec: PlatformSpec
) -> Dict[str, Any]:
    title = info.get("title") or f"{spec.name} media"
    thumbnail = info.get("best_thumbnail") or info.get("thumbnail")
    if spec.key == "youtube":
        thumbnail = extractors.extract_youtube_thumb(url) or thumbnail
    ext = "mp3" if requested == "mp3" else "mp4"
    return {
        "success": True,
        "platform": spec.key,
        "platform_name": spec.name,
        "title": title,
        "thumbnail": thumbnail,
        "duration": _duration_str(info.get("duration")),
        "uploader": info.get("uploader") or info.get("channel") or "",
        "view_count": info.get("view_count"),
        "download_url": stream_url,
        "url": stream_url,
        "stream_url": stream_url,
        "filename": safe_download_name(title, ext, spec.key),
        "quality": _quality_label(requested),
        "format": "MP3 Audio" if ext == "mp3" else "MP4 Video",
        "extension": ext,
        "formats": _format_payload(stream_url, requested, spec),
        "extractor": "yt-dlp",
    }


def _preview_only_result(
    title: str,
    thumbnail: str | None,
    duration: str | None,
    uploader: str,
    requested: str,
    spec: PlatformSpec,
    extractor: str,
    message: str,
) -> Dict[str, Any]:
    return {
        "success": True,
        "platform": spec.key,
        "platform_name": spec.name,
        "title": title or f"{spec.name} media",
        "thumbnail": thumbnail,
        "duration": duration,
        "uploader": uploader,
        "download_url": None,
        "url": None,
        "stream_url": None,
        "filename": safe_download_name(title or spec.key, "mp4", spec.key),
        "quality": _quality_label(requested),
        "format": "MP4 Video",
        "extension": "mp4",
        "formats": [],
        "extractor": extractor,
        "message": message,
    }


async def resolve_metadata(
    url: str, requested_format: str, spec: PlatformSpec
) -> Dict[str, Any]:
    """Resolve real media metadata for ``url``.

    Returns a dict ready to be serialised as the download API response.
    Raises :class:`LookupError` when no strategy could extract anything.
    """
    cache_key = make_cache_key("resolve", spec.key, url, requested_format)

    cached, layer = await cache.get(cache_key)
    if cached:
        cached = dict(cached)
        cached["cached"] = True
        cached["cache_layer"] = layer
        return cached

    async def _work() -> Dict[str, Any]:
        # ─ Strategy 1: platform fast path ───────────────────────────────────
        if spec.key == "tiktok":
            try:
                data = await asyncio.to_thread(extractors.extract_tiktok_media, url)
            except Exception as exc:
                logger.info("TikTok fast path failed: %s", exc)
                data = None
            if data and data.get("download_url"):
                return _tiktok_result(data, requested_format, spec)

        # ── Strategy 2: yt-dlp metadata (real stream URL) ───────────────────
        info = None
        try:
            info = await asyncio.wait_for(
                asyncio.to_thread(extract_media_with_ytdlp, url, spec),
                timeout=60,  # more time for Pinterest/Reddit/Threads/Facebook CDNs
            )
        except Exception as exc:
            logger.info("yt-dlp strategy failed for %s: %s", url, exc)

        if info:
            stream_url = pick_stream_url(info, requested_format)
            
            # Filter out manifest playlists — they are not directly playable.
            if stream_url and any(ext in stream_url.lower() for ext in (".m3u8", ".mpd")):
                stream_url = None

            if stream_url:
                result = _ytdlp_result(info, stream_url, url, requested_format, spec)
                # Flag platforms that need server-side merging (separate a/v streams)
                # Instagram always uses separate video+audio DASH streams — FFmpeg merge is required.
                if spec.key in ("reddit", "threads", "pinterest", "facebook"):
                    result["server_download_required"] = True
                return result

            thumbnail = info.get("best_thumbnail") or info.get("thumbnail")
            if spec.key == "youtube":
                thumbnail = extractors.extract_youtube_thumb(url) or thumbnail
            else:
                og = await asyncio.to_thread(extractors.fetch_opengraph_media, url)
                thumbnail = thumbnail or og.get("image")
                info["title"] = info.get("title") or og.get("title")
            return _preview_only_result(
                title=info.get("title") or f"{spec.name} media",
                thumbnail=thumbnail,
                duration=_duration_str(info.get("duration")),
                uploader=info.get("uploader") or info.get("channel") or "",
                requested=requested_format,
                spec=spec,
                extractor="yt-dlp",
                message=(
                    "Metadata was found, but this platform did not expose a direct "
                    "stream. Use the server-side download option instead."
                ),
            )

        # ── Strategy 3: OpenGraph ───────────────────────────────────────────
        og = await asyncio.to_thread(extractors.fetch_opengraph_media, url)
        thumbnail = og.get("image")
        if not thumbnail and spec.key == "youtube":
            thumbnail = extractors.extract_youtube_thumb(url)

        if og.get("title") or thumbnail:
            return _preview_only_result(
                title=og.get("title") or f"{spec.name} media",
                thumbnail=thumbnail,
                duration=None,
                uploader="",
                requested=requested_format,
                spec=spec,
                extractor="opengraph",
                message=(
                    "Only preview data was available for this link. Try the "
                    "server-side download option for a complete file."
                ),
            )

        raise LookupError(
            "Could not extract any media from this link. The post may be private, "
            "deleted or region-locked, or the platform is blocking automated access."
        )

    result = dict(await single_flight_info.do(cache_key, _work))
    result["cached"] = False
    if result.get("success"):
        await cache.set(
            cache_key,
            {k: v for k, v in result.items() if k not in ("cached", "cache_layer")},
            ttl=settings.METADATA_CACHE_TTL,
        )
    return result