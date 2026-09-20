"""Pydantic schemas shared by every router.

Field names are kept backwards compatible with the original per-project
projects (``download_url``, ``url``, ``filename``, ``quality``, ``format``,
``formats``, ``thumbnail``, ``duration``, ``uploader`` ...) so the existing
frontend JavaScript keeps working without changes.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PlatformEnum(str, Enum):
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    TWITTER = "twitter"
    PINTEREST = "pinterest"
    REDDIT = "reddit"
    SNAPCHAT = "snapchat"
    THREADS = "threads"
    TWITCH = "twitch"
    UNKNOWN = "unknown"


class ServiceStatusEnum(str, Enum):
    ONLINE = "ONLINE"
    MAINTENANCE = "MAINTENANCE"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"


class DownloadRequest(BaseModel):
    """Body accepted by every download endpoint.

    ``extra="allow"`` keeps old clients working: they used to send things like
    ``formats``, ``quality`` or ``engine`` that we can safely ignore.
    """

    url: str = Field(..., min_length=1, max_length=2048, description="Target media URL")
    option: Optional[str] = Field(
        default="best", description="Quality preset or option (e.g. 1080p, 720p, mp3)"
    )
    format: Optional[str] = Field(default=None, description="Requested format")
    quality: Optional[str] = Field(default=None, description="Quality preference")
    format_id: Optional[str] = Field(default=None, description="Format ID for multi-format sites")
    download: bool = Field(
        default=False,
        description="True = download the file to the server and return /api/file/<name>",
    )

    class Config:
        extra = "allow"


class DetectRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048)


class FormatOption(BaseModel):
    format_id: str
    quality: str
    ext: str
    url: Optional[str] = None
    filesize: Optional[str] = None
    has_audio: Optional[bool] = None
    has_video: Optional[bool] = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: str = "error"
    message: str
    platform: Optional[str] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    app: str
    version: str
    environment: str
    uptime_seconds: float
    platforms: Dict[str, Any]