"""URL validation shared by every platform router."""

from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

from .config import settings

BLOCKED_HOSTS = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
}

BLOCKED_PREFIXES = ("10.", "192.168.", "169.254.")


def validate_url(url: str) -> tuple[bool, Optional[str]]:
    """Return ``(is_valid, error_message)`` for a user supplied URL.

    Rejects empty input, oversized URLs, non-HTTP schemes and obvious SSRF
    targets (loopback / link-local / private ranges).
    """
    if not url or not url.strip():
        return False, "URL cannot be empty."

    trimmed = url.strip()
    if len(trimmed) > settings.MAX_URL_LENGTH:
        return False, f"URL is too long (max {settings.MAX_URL_LENGTH} characters)."

    parsed = urlparse(trimmed)
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        return False, "Only http and https URLs are supported."
    if scheme == "http" and not settings.ALLOW_HTTP:
        return False, "Only https URLs are supported."

    host = (parsed.hostname or "").lower()
    if not host:
        return False, "Could not determine the host from this URL."
    if host in BLOCKED_HOSTS or host.endswith(".local"):
        return False, "This host is not allowed."
    if host.startswith(BLOCKED_PREFIXES) or host.startswith("172.16."):
        return False, "This host is not allowed."

    return True, None


def origin_of(request_base_url: str) -> str:
    """Normalise a FastAPI ``request.base_url`` into a clean origin string."""
    return (request_base_url or "").rstrip("/")