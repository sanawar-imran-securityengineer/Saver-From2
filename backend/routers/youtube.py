"""YouTube downloader API — ``/api/youtube/*``.

Built from the shared factory so all platforms expose an identical surface.
"""

from ..utils.platforms import get_platform
from .platform_router import build_platform_router

router = build_platform_router(get_platform("youtube"))

__all__ = ["router"]