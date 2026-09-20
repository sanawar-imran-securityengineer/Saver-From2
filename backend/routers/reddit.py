"""Reddit downloader API — ``/api/reddit/*``."""

from ..utils.platforms import get_platform
from .platform_router import build_platform_router

router = build_platform_router(get_platform("reddit"))

__all__ = ["router"]