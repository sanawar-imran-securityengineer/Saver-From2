"""Shared file serving — ``/api/file/<filename>``.

Preserved from the original per-platform services so any already-integrated
client that expects ``/api/file/<name>`` keeps working.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..utils.config import settings
from ..utils.security import resolve_safe_path

router = APIRouter(tags=["Files"])


@router.get("/api/file/{filename}")
async def serve_file(filename: str) -> FileResponse:
    """Serve a downloaded file. Only server-generated UUID names are allowed."""
    safe_path: Path | None = resolve_safe_path(filename, settings.DOWNLOADS_DIR)
    if safe_path is None or not safe_path.exists():
        raise HTTPException(status_code=404, detail="File not found or expired.")

    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if safe_path.stat().st_size > max_bytes:
        raise HTTPException(status_code=413, detail="File too large to serve.")

    media_type = "audio/mpeg" if safe_path.suffix.lower() == ".mp3" else "video/mp4"
    return FileResponse(
        path=str(safe_path),
        media_type=media_type,
        filename=safe_path.name,
        headers={
            "Cache-Control": "public, max-age=1800",
            "Content-Disposition": f'attachment; filename="{safe_path.name}"',
        },
    )