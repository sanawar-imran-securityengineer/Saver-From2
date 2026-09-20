"""Facebook downloader API — ``/api/facebook/*``.

Kept even though Facebook is not in the required frontend route list, because
the original platform already shipped a Facebook page and card.
"""

from ..utils.platforms import get_platform
from .platform_router import build_platform_router

router = build_platform_router(get_platform("facebook"))

__all__ = ["router"]