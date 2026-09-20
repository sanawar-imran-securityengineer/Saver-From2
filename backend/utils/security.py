"""Security helpers preserved from the original per-platform services.

* structured JSON logging
* secret redaction before a URL is logged
* strict whitelisting of servable filenames (UUID names only) so that
  ``/api/file/<name>`` can never be used for path traversal.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger("saverfrom.security")

UUID_STEM_RE = re.compile(r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$")
ALLOWED_EXTENSIONS = {".mp4", ".mp3", ".webm", ".m4a", ".jpg", ".jpeg", ".png", ".webp"}

SENSITIVE_PATTERNS = [
    re.compile(r"(?:password|passwd|pwd|token|secret|key|cookie|auth)=[^\s&]*", re.IGNORECASE),
    re.compile(r"ai=[^&]+", re.IGNORECASE),
]


def setup_logging(level: int = logging.INFO) -> None:
    """Install a single JSON-ish stream handler on the root logger."""
    root = logging.getLogger()
    root.setLevel(level)
    if root.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            fmt='{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    root.addHandler(handler)


def sanitize_url(url: str) -> str:
    """Strip anything that looks like a credential out of a URL."""
    safe = url or ""
    for pattern in SENSITIVE_PATTERNS:
        safe = pattern.sub("[REDACTED]", safe)
    return safe


def secure_log(message: str, url: Optional[str] = None, **kwargs) -> None:
    """Log a structured message, sanitising any URL that may contain secrets."""
    extra = {}
    if url:
        extra["url"] = sanitize_url(url)
    extra.update(
        {k: v for k, v in kwargs.items() if k not in ("password", "token", "secret", "cookie")}
    )
    logger.info(json.dumps({"message": message, **extra}))


def new_file_id() -> str:
    """Generate the UUID stem used for every downloaded file."""
    return str(uuid.uuid4())


def validate_filename(filename: str) -> bool:
    """Only server-generated UUID filenames may be served back to a client."""
    if not filename or len(filename) > 255:
        return False
    if filename.startswith(".") or "/" in filename or "\\" in filename or ".." in filename:
        return False
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        return False
    return bool(UUID_STEM_RE.match(Path(filename).stem))


def resolve_safe_path(filename: str, base_dir: Path) -> Optional[Path]:
    """Resolve ``filename`` inside ``base_dir`` and confirm it stays inside."""
    if not validate_filename(filename):
        return None
    base_resolved = base_dir.resolve()
    candidate = (base_dir / filename).resolve()
    try:
        candidate.relative_to(base_resolved)
    except ValueError:
        return None
    return candidate


def safe_download_name(title: str, extension: str, fallback: str = "media") -> str:
    """Build a friendly, filesystem-safe attachment name from a media title."""
    cleaned = "".join(
        ch for ch in (title or "") if ch.isalnum() or ch in " -_()[]."
    ).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)[:60].strip() or fallback
    extension = extension.lstrip(".").lower() or "mp4"
    return f"{cleaned}.{extension}"