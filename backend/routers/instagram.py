"""Instagram downloader API — ``/api/instagram/*``.

Includes the carousel/reel/story aware metadata that the original Instagram
service exposed through its ``/api/v1/*`` router.
"""

from ..utils.platforms import get_platform
from .platform_router import build_platform_router

router = build_platform_router(get_platform("instagram"))

__all__ = ["router"]