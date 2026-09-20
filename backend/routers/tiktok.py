"""TikTok downloader API — ``/api/tiktok/*``.

TikTok also has a dedicated fast path (public tikwm API) inside the resolver,
which returns a watermark-free MP4 without touching yt-dlp.
"""

from ..utils.platforms import get_platform
from .platform_router import build_platform_router

router = build_platform_router(get_platform("tiktok"))

__all__ = ["router"]