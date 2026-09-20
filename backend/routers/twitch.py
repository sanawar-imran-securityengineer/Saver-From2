"""Twitch downloader API — ``/api/twitch/*``."""

from ..utils.platforms import get_platform
from .platform_router import build_platform_router

router = build_platform_router(get_platform("twitch"))

__all__ = ["router"]