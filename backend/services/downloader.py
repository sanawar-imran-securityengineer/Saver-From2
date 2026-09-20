"""Real server-side downloader — preserved from the working services.

This is the module that actually writes files to disk. It is deliberately kept
faithful to the original implementation:

* yt-dlp with the same resilient base options (retries, socket timeout,
  browser-like headers)
* ``%(ext)s`` output templates with a UUID stem so the produced filename is
  unpredictable and safe to serve (see ``utils.security.resolve_safe_path``)
* FFmpeg audio extraction for MP3 and ``merge_output_format="mp4"`` for video
* retry loop honouring ``MAX_RETRIES``
* a semaphore enforcing ``MAX_CONCURRENT_DOWNLOADS``
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from ..utils.config import settings
from ..utils.security import new_file_id
from ..utils.platforms import PlatformSpec

logger = logging.getLogger("saverfrom.downloader")


class DownloadError(Exception):
    """Raised when a download could not be completed."""


@dataclass
class DownloadResult:
    title: str
    filename: str
    option_requested: str
    quality_selected: str
    downloader_used: str
    download_url: str
    file_size: Optional[str] = None
    platform: Optional[str] = None
    thumbnail: Optional[str] = None
    duration: Optional[str] = None


# Height-capped selector templates: prefer mp4+m4a, fall back to anything.
FORMAT_MAP: Dict[str, str] = {
    "360p": "bv*[height<=360][ext=mp4]+ba[ext=m4a]/bv*[height<=360]+ba/b[height<=360]/b",
    "480p": "bv*[height<=480][ext=mp4]+ba[ext=m4a]/bv*[height<=480]+ba/b[height<=480]/b",
    "720p": "bv*[height<=720][ext=mp4]+ba[ext=m4a]/bv*[height<=720]+ba/b[height<=720]/b",
    "1080p": "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]/b",
    "1440p": "bv*[height<=1440][ext=mp4]+ba[ext=m4a]/bv*[height<=1440]+ba/b[height<=1440]/b",
    "2160p": "bv*[height<=2160][ext=mp4]+ba[ext=m4a]/bv*[height<=2160]+ba/b[height<=2160]/b",
    "4k": "bv*[height<=2160][ext=mp4]+ba[ext=m4a]/bv*[height<=2160]+ba/b/b",
    "best": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b",
    "mp3": "bestaudio/best",
}

QUALITY_HEIGHTS: Dict[str, int] = {
    "360p": 360,
    "480p": 480,
    "720p": 720,
    "1080p": 1080,
    "1440p": 1440,
    "2160p": 2160,
    "4k": 2160,
}


def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def ffmpeg_available() -> bool:
    """True when ffmpeg is reachable (needed for MP3 and merged video)."""
    if settings.FFMPEG_LOCATION and Path(settings.FFMPEG_LOCATION).exists():
        return True
    return bool(shutil.which("ffmpeg"))


class YtDlpDownloader:
    """yt-dlp based downloader that writes a real file into the downloads dir."""

    name = "yt-dlp"

    def base_opts(self, spec: Optional[PlatformSpec] = None) -> Dict[str, Any]:
        from .ytdlp import ydl_base_opts

        opts = ydl_base_opts(spec)
        opts["skip_download"] = False
        opts["restrictfilenames"] = True
        opts["socket_timeout"] = 20
        opts["retries"] = 1
        opts["extractor_retries"] = 1
        opts["fragment_retries"] = 1
        opts["concurrent_fragment_downloads"] = 8
        opts["http_chunk_size"] = 10485760
        if settings.FFMPEG_LOCATION:
            opts["ffmpeg_location"] = settings.FFMPEG_LOCATION
        return opts

    def build_opts(
        self,
        option: str,
        file_id: str,
        output_directory: Path,
        spec: Optional[PlatformSpec] = None,
    ) -> Dict[str, Any]:
        opts = self.base_opts(spec)
        # %(ext)s lets yt-dlp name the file after post-processing/merging.
        opts["outtmpl"] = str(Path(output_directory) / f"{file_id}.%(ext)s")

        if option == "mp3":
            audio_fmt = "bestaudio/best"
            if spec is not None and spec.key == "youtube":
                audio_fmt = "bestaudio/18/b"
            opts["format"] = audio_fmt
            if ffmpeg_available():
                opts["postprocessors"] = [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ]
        else:
            fmt = FORMAT_MAP.get(option, FORMAT_MAP["best"])
            if spec is not None and spec.key == "youtube":
                # YouTube currently serves SABR adaptive streams without a
                # direct URL. Progressive itag 18 still works; merge selectors
                # (bv*+ba) fail even when ffmpeg is installed.
                opts["format"] = "18/22/b[ext=mp4]/b"
            else:
                opts.update(
                    {
                        "format": fmt,
                        "merge_output_format": "mp4",
                    }
                )
        return opts

    def extract_info_sync(self, url: str, spec: Optional[PlatformSpec] = None) -> Dict[str, Any]:
        """Metadata only (``download=False``)."""
        import yt_dlp

        opts = self.base_opts(spec)
        opts["skip_download"] = True
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        if not info:
            raise DownloadError("Could not extract media metadata")
        return info

    # ── real download to disk ────────────────────────────────────────────────
    def download_sync(
        self,
        url: str,
        output_directory: Path,
        option: str,
        spec: Optional[PlatformSpec] = None,
    ) -> DownloadResult:
        import yt_dlp

        output_directory = Path(output_directory)
        output_directory.mkdir(parents=True, exist_ok=True)
        file_id = new_file_id()
        ydl_opts = self.build_opts(option, file_id, output_directory, spec)

        attempts = 0
        last_error: Optional[Exception] = None

        while attempts <= settings.MAX_RETRIES:
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True) or {}

                title = info.get("title") or "Untitled media"
                expected_ext = "mp3" if option == "mp3" else "mp4"
                expected_path = output_directory / f"{file_id}.{expected_ext}"

                if not expected_path.exists():
                    for candidate in output_directory.glob(f"{file_id}.*"):
                        if candidate.suffix.lower() in (".mp4", ".mp3", ".webm", ".m4a"):
                            expected_path = candidate
                            break

                if not expected_path.exists():
                    raise DownloadError("Output file was not created")

                size_bytes = expected_path.stat().st_size
                if size_bytes > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
                    try:
                        expected_path.unlink()
                    except Exception:
                        pass
                    raise DownloadError(
                        f"File exceeds the {settings.MAX_FILE_SIZE_MB} MB limit"
                    )

                quality_selected = option
                if option != "mp3":
                    height = info.get("height")
                    cap = QUALITY_HEIGHTS.get(option)
                    if height and cap and height < cap:
                        quality_selected = f"{height}p"

                duration = info.get("duration")
                return DownloadResult(
                    title=title,
                    filename=expected_path.name,
                    option_requested=option,
                    quality_selected=quality_selected,
                    downloader_used=self.name,
                    download_url=f"/api/file/{expected_path.name}",
                    file_size=format_size(size_bytes),
                    platform=spec.key if spec else None,
                    thumbnail=info.get("thumbnail"),
                    duration=(
                        f"{int(duration // 60):02d}:{int(duration % 60):02d}"
                        if duration
                        else None
                    ),
                )

            except DownloadError:
                raise
            except Exception as exc:  # includes yt_dlp.utils.DownloadError
                last_error = exc
                attempts += 1
                if attempts <= settings.MAX_RETRIES:
                    logger.warning(
                        "Download attempt %s/%s failed, retrying: %s",
                        attempts,
                        settings.MAX_RETRIES + 1,
                        exc,
                    )
                else:
                    break

        raise DownloadError(
            f"Download failed after {attempts} attempt(s): {last_error}"
        ) from last_error

    async def download(
        self,
        url: str,
        output_directory: Path,
        option: str,
        spec: Optional[PlatformSpec] = None,
    ) -> DownloadResult:
        return await asyncio.to_thread(
            self.download_sync, url, output_directory, option, spec
        )

    async def extract_info(self, url: str, spec: Optional[PlatformSpec] = None) -> Dict[str, Any]:
        return await asyncio.to_thread(self.extract_info_sync, url, spec)


class DownloaderManager:
    """Owns the downloader instance and enforces the concurrency limit."""

    def __init__(self, max_concurrent: Optional[int] = None):
        self.downloader = YtDlpDownloader()
        self._semaphore = asyncio.Semaphore(max_concurrent or settings.MAX_CONCURRENT_DOWNLOADS)

    async def download(
        self,
        url: str,
        output_directory: Path,
        option: str,
        spec: Optional[PlatformSpec] = None,
        timeout: Optional[int] = None,
    ) -> DownloadResult:
        async with self._semaphore:
            return await asyncio.wait_for(
                self.downloader.download(url, output_directory, option, spec),
                timeout=timeout or settings.DOWNLOAD_TIMEOUT_SECONDS,
            )

    async def info(self, url: str, spec: Optional[PlatformSpec] = None) -> Dict[str, Any]:
        return await self.downloader.extract_info(url, spec)


# Shared singleton used by every router.
downloader_manager = DownloaderManager()