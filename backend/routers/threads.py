"""Threads downloader API — ``/api/threads/*``."""

from ..utils.platforms import get_platform
from .platform_router import build_platform_router

router = build_platform_router(get_platform("threads"))

__all__ = ["router"]