"""URL platform detection.

Uses the host patterns declared in :mod:`backend.utils.platforms`, so adding a
platform there automatically makes detection work.
"""

from __future__ import annotations

from typing import Optional, Tuple
from urllib.parse import urlparse

from .models import PlatformEnum
from .platforms import ENUM_TO_KEY, PLATFORMS


def normalize_url(url: str) -> str:
    """Ensure the URL has a scheme and no surrounding whitespace."""
    trimmed = (url or "").strip()
    if not trimmed:
        return ""
    if not trimmed.startswith(("http://", "https://")):
        trimmed = "https://" + trimmed
    return trimmed


def detect_platform(raw_url: str) -> Tuple[PlatformEnum, Optional[str]]:
    """Identify which platform a URL belongs to.

    Returns ``(PlatformEnum, error_message)``.
    """
    if not raw_url or not raw_url.strip():
        return PlatformEnum.UNKNOWN, "URL cannot be empty."

    url = normalize_url(raw_url)
    try:
        hostname = (urlparse(url).hostname or "").lower()
    except Exception:
        return PlatformEnum.UNKNOWN, "Invalid URL format."

    if not hostname:
        return PlatformEnum.UNKNOWN, "Could not determine hostname from URL."

    for spec in PLATFORMS:
        if spec.regex.search(url):
            return PlatformEnum(spec.key), None

    return (
        PlatformEnum.UNKNOWN,
        "Unsupported video URL. Please provide a link from a supported platform.",
    )


def detect_platform_key(raw_url: str) -> Tuple[Optional[str], Optional[str]]:
    """Convenience wrapper returning the platform *key* (e.g. ``"youtube"``)."""
    platform_enum, error = detect_platform(raw_url)
    if error:
        return None, error
    return ENUM_TO_KEY.get(platform_enum.value), None