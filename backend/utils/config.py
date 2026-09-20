"""Central configuration for the unified SaverFrom backend.

All values come from environment variables (or a local ``.env`` file) so the
same code runs unchanged in development and on Hostinger.  Every default is a
safe, working value: with NO ``.env`` present the app still boots and downloads.
"""

from pathlib import Path
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parent.parent      # .../backend
PROJECT_ROOT = BACKEND_DIR.parent                          # repository root
FRONTEND_DIR = PROJECT_ROOT / "frontend"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Application ───────────────────────────────────────────────────────────
    APP_NAME: str = "SaverFrom"
    APP_VERSION: str = "3.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"   # development | production

    # ── Server ───────────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1
    ROOT_PATH: str = ""                # set when mounted on a sub-path

    # ── Storage / download limits ─────────────────────────────────────────────
    DOWNLOADS_DIR: Path = BACKEND_DIR / "downloads"
    MAX_FILE_SIZE_MB: int = 500
    DOWNLOAD_TIMEOUT_SECONDS: int = 300
    FILE_TTL_MINUTES: int = 30
    MAX_CONCURRENT_DOWNLOADS: int = 3
    MAX_RETRIES: int = 2
    CLEANUP_INTERVAL_SECONDS: int = 60

    # ── Metadata cache (in-process, used by the unified endpoint) ─────────────
    METADATA_CACHE_TTL: int = 900       # 15 minutes

    # ── Multi-layer cache ─────────────────────────────────────────────────────
    REDIS_URL: str = ""                 # empty -> L1 in-memory cache only
    CACHE_TTL: int = 3600
    CACHE_L1_MAXSIZE: int = 2000
    CACHE_L1_TTL: int = 300
    CACHE_L2_TTL: int = 3600
    CACHE_INFO_TTL: int = 600

    # ── CORS ──────────────────────────────────────────────────────────────────
    # "*" (default) keeps the app working out of the box.  In production set
    # CORS_ORIGINS to the real frontend origins, e.g.
    #   CORS_ORIGINS=https://saverfrom.com,https://www.saverfrom.com
    CORS_ORIGINS: str = "*"
    ALLOWED_HOSTS: str = "*"

    # ── Rate limiting / validation ────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 60
    MAX_URL_LENGTH: int = 2048
    ALLOW_HTTP: bool = False

    # ── yt-dlp ────────────────────────────────────────────────────────────────
    YDL_TIMEOUT: int = 30
    YDL_RETRIES: int = 3

    # ── Optional FFmpeg location (only needed for MP3/merged 1080p) ───────────
    # Point this at a folder that contains ffmpeg/ffprobe if they are not on
    # the system PATH.  Example: /home/u123456/ffmpeg/bin
    FFMPEG_LOCATION: str = ""

    # ── Validators / helpers ──────────────────────────────────────────────────
    @field_validator("DOWNLOADS_DIR", mode="before")
    @classmethod
    def _expand_downloads_dir(cls, value):
        if isinstance(value, str) and value.strip():
            return Path(value).expanduser()
        return value

    @property
    def cors_origins_list(self) -> List[str]:
        """CORS origins as a list. ``*`` means 'allow everything'."""
        raw = (self.CORS_ORIGINS or "").strip()
        if not raw or raw == "*":
            return ["*"]
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    @property
    def cors_allow_credentials(self) -> bool:
        # Credentials cannot be combined with a wildcard origin.
        return "*" not in self.cors_origins_list

    @property
    def allowed_hosts_list(self) -> List[str]:
        raw = (self.ALLOWED_HOSTS or "").strip()
        if not raw or raw == "*":
            return ["*"]
        return [host.strip() for host in raw.split(",") if host.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() in ("production", "prod")


settings = Settings()

# Make sure the download directory exists as early as possible.
settings.DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)