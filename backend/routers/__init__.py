"""API routers.

Each platform router is imported from its own module so the file layout mirrors
the required structure, while the actual endpoint bodies live once in
``platform_router.py`` (no duplicated logic).
"""

from . import (
    admin,
    facebook,
    files,
    health,
    instagram,
    pinterest,
    reddit,
    snapchat,
    threads,
    tiktok,
    twitch,
    twitter,
    unified,
    youtube,
)

# Ordered so the documentation groups sensibly and the more specific paths win.
PLATFORM_ROUTERS = [
    youtube.router,
    tiktok.router,
    instagram.router,
    facebook.router,
    twitter.router,
    pinterest.router,
    reddit.router,
    snapchat.router,
    threads.router,
    twitch.router,
]

CORE_ROUTERS = [
    unified.router,
    files.router,
    health.router,
    admin.router,
]

ALL_ROUTERS = CORE_ROUTERS + PLATFORM_ROUTERS

# Static, explicit redirect map: /<platform> -> the downloader page.
# Kept as data so main.py stays tiny and pytest can assert against it.
PLATFORM_PAGES = {
    "youtube": "youtube.html",
    "tiktok": "tiktok.html",
    "instagram": "instagram.html",
    "facebook": "facebook.html",
    "twitter": "twitter.html",
    "pinterest": "pinterest.html",
    "reddit": "reddit.html",
    "snapchat": "snapchat.html",
    "threads": "threads.html",
    "twitch": "twitch.html",
}

EXTRA_PAGES = {
    "blog": "blog.html",
    "about": "about.html",
    "contact": "contact.html",
    "privacy-policy": "privacy-policy.html",
    "terms-of-service": "terms-of-service.html",
    "copyright": "copyright.html",
    "disclaimer": "disclaimer.html",
}

__all__ = [
    "ALL_ROUTERS",
    "CORE_ROUTERS",
    "PLATFORM_ROUTERS",
    "PLATFORM_PAGES",
    "EXTRA_PAGES",
]