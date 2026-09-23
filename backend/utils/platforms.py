"""Single source of truth for every supported downloader platform.

Adding a platform here automatically registers:

* URL detection                  (``backend.utils.detector``)
* ``/api/<platform>/...`` router (``backend.routers.<platform>``)
* the ``/api/platforms`` listing used by the frontend
* the ``/api/v1/health`` per-platform status block

Nothing else in the codebase hard-codes a platform list.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Pattern, Tuple

from .models import PlatformEnum


@dataclass(frozen=True)
class PlatformSpec:
    """Static definition of one downloader."""

    key: str                      # url/route key, e.g. "youtube"
    name: str                     # human name, e.g. "YouTube"
    icon: str                     # icon path served by the frontend
    accent_color: str             # brand colour used by the UI
    page: str                     # relative frontend page inside /pages
    host_patterns: Tuple[str, ...] = ()   # regex matched against the whole URL
    sample_url: str = ""
    formats: Tuple[str, ...] = ("360p", "720p", "1080p", "mp3")
    options: Tuple[Tuple[str, str], ...] = ()   # (value, label) pills in the UI
    needs_ffmpeg: bool = False    # True when merging / audio extraction is used

    @property
    def regex(self) -> Pattern[str]:
        return re.compile("|".join(self.host_patterns), re.IGNORECASE)

    @property
    def option_pairs(self) -> Tuple[Tuple[str, str], ...]:
        if self.options:
            return self.options
        return tuple((fmt, DEFAULT_OPTION_LABELS.get(fmt, fmt)) for fmt in self.formats)


DEFAULT_OPTION_LABELS: Dict[str, str] = {
    "360p": "360p SD",
    "480p": "480p",
    "720p": "720p HD",
    "1080p": "1080p Full HD",
    "1440p": "1440p QHD",
    "2160p": "2160p 4K",
    "4k": "4K UHD",
    "mp3": "Audio MP3",
    "best": "Best available",
}


def _specs() -> List[PlatformSpec]:
    return [
        PlatformSpec(
            key="youtube",
            name="YouTube",
            icon="/static/icons/youtube.svg",
            accent_color="#FF0000",
            page="youtube.html",
            host_patterns=(
                r"^(?:https?://)?(?:[a-zA-Z0-9_\-]+\.)?(?:youtube\.com|youtu\.be|youtube-nocookie\.com)",
            ),
            sample_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            formats=("360p", "720p", "1080p", "1440p", "2160p", "mp3"),
            needs_ffmpeg=True,
        ),
        PlatformSpec(
            key="tiktok",
            name="TikTok",
            icon="/static/icons/tiktok.svg",
            accent_color="#010101",
            page="tiktok.html",
            host_patterns=(
                r"^(?:https?://)?(?:[a-zA-Z0-9_\-]+\.)?(?:tiktok\.com|douyin\.com)",
            ),
            sample_url="https://www.tiktok.com/@tiktok/video/7106594312292453675",
            formats=("best", "mp3"),
            options=(("best", "No Watermark MP4"), ("mp3", "Audio MP3")),
        ),
        PlatformSpec(
            key="instagram",
            name="Instagram",
            icon="/static/icons/instagram.svg",
            accent_color="#E1306C",
            page="instagram.html",
            host_patterns=(
                r"^(?:https?://)?(?:[a-zA-Z0-9_\-]+\.)?(?:instagram\.com|instagr\.am)",
            ),
            sample_url="https://www.instagram.com/reel/CtjoC2BNsB2/",
            formats=("720p", "1080p", "mp3"),
        ),
        PlatformSpec(
            key="facebook",
            name="Facebook",
            icon="/static/icons/facebook.svg",
            accent_color="#1877F2",
            page="facebook.html",
            host_patterns=(
                r"^(?:https?://)?(?:[a-zA-Z0-9_\-]+\.)?(?:facebook\.com|fb\.watch|fb\.com|fb\.me)",
            ),
            sample_url="https://www.facebook.com/watch/?v=10153231379946729",
            formats=("360p", "720p", "1080p"),
        ),
        PlatformSpec(
            key="twitter",
            name="Twitter / X",
            icon="/static/icons/twitter.svg",
            accent_color="#1DA1F2",
            page="twitter.html",
            host_patterns=(
                r"^(?:https?://)?(?:[a-zA-Z0-9_\-]+\.)?(?:twitter\.com|x\.com|t\.co)",
            ),
            sample_url="https://twitter.com/i/status/1234567890123456789",
            formats=("720p", "1080p", "mp3"),
        ),
        PlatformSpec(
            key="pinterest",
            name="Pinterest",
            icon="/static/icons/pinterest.svg",
            accent_color="#E60023",
            page="pinterest.html",
            host_patterns=(
                r"^(?:https?://)?(?:[a-zA-Z0-9_\-]+\.)?(?:pinterest\.[a-z.]+|pin\.it)",
            ),
            sample_url="https://www.pinterest.com/pin/1234567890/",
            formats=("best", "1080p", "mp3"),
            options=(("best", "Best available"), ("1080p", "1080p Full HD"), ("mp3", "Audio MP3")),
        ),
        PlatformSpec(
            key="reddit",
            name="Reddit",
            icon="/static/icons/reddit.svg",
            accent_color="#FF4500",
            page="reddit.html",
            host_patterns=(
                r"^(?:https?://)?(?:[a-zA-Z0-9_\-]+\.)?(?:reddit\.com|redd\.it|v\.redd\.it)",
            ),
            sample_url="https://www.reddit.com/r/aww/comments/xxxxxx/",
            formats=("720p", "1080p", "mp3"),
            needs_ffmpeg=True,
        ),
        PlatformSpec(
            key="snapchat",
            name="Snapchat",
            icon="/static/icons/snapchat.svg",
            accent_color="#FFFC00",
            page="snapchat.html",
            host_patterns=(
                r"^(?:https?://)?(?:[a-zA-Z0-9_\-]+\.)?(?:snapchat\.com)",
            ),
            sample_url="https://www.snapchat.com/spotlight/xxxxxxxx",
            formats=("720p", "1080p"),
        ),
        PlatformSpec(
            key="threads",
            name="Threads",
            icon="/static/icons/threads.svg",
            accent_color="#000000",
            page="threads.html",
            host_patterns=(
                r"^(?:https?://)?(?:[a-zA-Z0-9_\-]+\.)?(?:threads\.net|threads\.com)",
            ),
            sample_url="https://www.threads.net/@zuck/post/xxxxxxxx",
            formats=("720p", "1080p", "mp3"),
        ),
        PlatformSpec(
            key="twitch",
            name="Twitch",
            icon="/static/icons/twitch.svg",
            accent_color="#9146FF",
            page="twitch.html",
            host_patterns=(
                r"^(?:https?://)?(?:[a-zA-Z0-9_\-]+\.)?(?:twitch\.tv|clips\.twitch\.tv)",
            ),
            sample_url="https://www.twitch.tv/videos/1234567890",
            formats=("720p", "1080p", "mp3"),
        ),
    ]


PLATFORMS: List[PlatformSpec] = _specs()
PLATFORMS_BY_KEY: Dict[str, PlatformSpec] = {spec.key: spec for spec in PLATFORMS}

# Map the URL-detector enum values onto platform route keys.
ENUM_TO_KEY: Dict[str, str] = {
    PlatformEnum.YOUTUBE.value: "youtube",
    PlatformEnum.TIKTOK.value: "tiktok",
    PlatformEnum.INSTAGRAM.value: "instagram",
    PlatformEnum.FACEBOOK.value: "facebook",
    PlatformEnum.TWITTER.value: "twitter",
    PlatformEnum.PINTEREST.value: "pinterest",
    PlatformEnum.REDDIT.value: "reddit",
    PlatformEnum.SNAPCHAT.value: "snapchat",
    PlatformEnum.THREADS.value: "threads",
    PlatformEnum.TWITCH.value: "twitch",
}


def get_platform(key: str) -> PlatformSpec:
    """Return the spec for ``key``.

    Raises ``KeyError`` when the platform is unknown so callers can turn it
    into a clean HTTP 404.
    """
    try:
        return PLATFORMS_BY_KEY[key]
    except KeyError:
        raise KeyError(f"Unknown platform: {key}") from None


def platform_keys() -> List[str]:
    """All registered platform route keys, in display order."""
    return [spec.key for spec in PLATFORMS]