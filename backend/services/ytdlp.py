"""yt-dlp metadata extraction with sane platform-specific tuning."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..utils.platforms import PlatformSpec
from .extractors import _ytdlp_base_opts

logger = logging.getLogger("saverfrom.extractors.ytdlp")


def _platform_overrides(spec: Optional[PlatformSpec]) -> Dict[str, Any]:
    """Per-platform yt-dlp tweaks that measurably improve success rate."""
    if spec is None:
        return {}
    if spec.key == "youtube":
        # One Android client is enough for itag 18 and avoids sequential
        # webpage/ios/mweb round-trips that make fetch/download slow.
        return {
            "extractor_args": {
                "youtube": {
                    "player_client": ["android"],
                }
            },
            "socket_timeout": 15,
        }
    if spec.key in ("instagram", "facebook", "threads"):
        return {"http_headers": {"User-Agent": "facebookexternalhit/1.1"}}
    return {}


def ydl_base_opts(spec: Optional[PlatformSpec] = None) -> Dict[str, Any]:
    opts = _ytdlp_base_opts()
    opts.update(_platform_overrides(spec))
    return opts


def _is_storyboard_url(url: str) -> bool:
    text = (url or "").lower()
    return "storyboard" in text or "/sb/" in text or "i.ytimg.com/sb/" in text


def _is_media_url(url: Optional[str]) -> bool:
    text = (url or "").lower()
    if not text or _is_storyboard_url(text):
        return False
    if any(token in text for token in (".jpg", ".png", ".webp", ".mhtml")):
        return False
    return True


def _pick_thumbnail(
    info: Dict[str, Any], page_url: str, spec: Optional[PlatformSpec]
) -> Optional[str]:
    if spec is not None and spec.key == "youtube":
        from .extractors import extract_youtube_thumb

        guaranteed = extract_youtube_thumb(page_url or info.get("webpage_url") or "")
        if guaranteed:
            return guaranteed
    thumb = info.get("thumbnail")
    if thumb and not _is_storyboard_url(thumb):
        return thumb
    usable = [
        t
        for t in (info.get("thumbnails") or [])
        if t.get("url") and not _is_storyboard_url(t.get("url", ""))
    ]
    if not usable:
        return None if (thumb and _is_storyboard_url(thumb)) else thumb
    return max(
        usable, key=lambda t: (t.get("width") or 0) * (t.get("height") or 0)
    ).get("url") or thumb


def extract_media_with_ytdlp(
    url: str, spec: Optional[PlatformSpec] = None
) -> Optional[Dict[str, Any]]:
    """Extract metadata only (``download=False``). Returns the raw info dict.

    ``info["best_thumbnail"]`` is added so callers do not have to walk the
    ``thumbnails`` list themselves.
    """
    import yt_dlp

    opts = ydl_base_opts(spec)
    if spec is not None and spec.key == "youtube":
        opts["format"] = "18/best"
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        logger.info("yt-dlp metadata extraction failed for %s: %s", url, exc)
        return None

    if not info:
        return None

    info["best_thumbnail"] = _pick_thumbnail(info, url, spec)
    return info


def pick_stream_url(info: Dict[str, Any], requested_format: str = "best") -> Optional[str]:
    """Choose a progressive/direct stream URL for the requested format.

    Mirrors the original gateway behaviour, including the audio-only branch for
    ``mp3`` requests.
    """
    formats = [f for f in (info.get("formats") or []) if _is_media_url(f.get("url"))]

    if requested_format == "mp3":
        audio_only = [f for f in formats if f.get("vcodec") == "none"]
        if audio_only:
            return audio_only[-1]["url"]
        return info.get("url") if _is_media_url(info.get("url")) else None

    if requested_format in ("best", "", None):
        if _is_media_url(info.get("url")):
            return info["url"]
        progressive = [
            f for f in formats if f.get("vcodec") != "none" and f.get("acodec") != "none"
        ]
        if progressive:
            return progressive[-1]["url"]
        return formats[-1]["url"] if formats else None

    target_height = 0
    if requested_format.endswith("p"):
        try:
            target_height = int(requested_format[:-1])
        except ValueError:
            target_height = 0

    if target_height:
        height_matched = [
            f
            for f in formats
            if (f.get("height") or 0) and (f.get("height") or 0) <= target_height
        ]
        if height_matched:
            height_matched.sort(key=lambda f: f.get("height") or 0)
            return height_matched[-1]["url"]

    candidate = info.get("url") if _is_media_url(info.get("url")) else None
    return candidate or (formats[-1]["url"] if formats else None)
