"""Twitter / X downloader API — ``/api/twitter/*``."""

from ..utils.platforms import get_platform
from .platform_router import build_platform_router

router = build_platform_router(get_platform("twitter"))

__all__ = ["router"]