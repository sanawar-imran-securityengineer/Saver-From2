import asyncio
import uuid
import logging
import os
from pathlib import Path
from typing import Optional

import yt_dlp

from .base import BaseDownloader
from .result import DownloadResult
from ..config import settings

logger = logging.getLogger("swiftfetch.ytdlp")

# Reddit uses DASH format — video and audio are separate streams (mp4 container).
# Format strings: prefer mp4 video + any audio, fallback to merged best, then single best.
FORMAT_MAP = {
    "360p":  "bv*[height<=360][ext=mp4]+ba/bv*[height<=360]+ba[ext=m4a]/bv*[height<=360]+ba/b[height<=360]/best",
    "720p":  "bv*[height<=720][ext=mp4]+ba/bv*[height<=720]+ba[ext=m4a]/bv*[height<=720]+ba/b[height<=720]/best",
    "1080p": "bv*[height<=1080][ext=mp4]+ba/bv*[height<=1080]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]/best",
    "mp3":   "bestaudio/best",
}

QUALITY_HEIGHTS = {
    "360p": 360,
    "720p": 720,
    "1080p": 1080,
}

# FFmpeg path — explicitly set so yt-dlp can merge Reddit DASH audio+video streams.
# Reddit stores video and audio as separate DASH streams; FFmpeg is required to merge them.
_FFMPEG_LOCATION = r"C:\Users\7iha7\AppData\Local\Microsoft\WinGet\Packages\yt-dlp.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-N-125875-g5d4d3bdc61-win64-gpl\bin"

# Common optimized yt-dlp base options for all operations
_BASE_OPTS = {
    "noplaylist": True,
    "restrictfilenames": True,
    "quiet": True,
    "no_warnings": True,
    "noprogress": True,
    "no_color": True,
    # FFmpeg location for merging Reddit DASH video+audio streams
    "ffmpeg_location": _FFMPEG_LOCATION,
    # Network resilience
    "socket_timeout": 30,
    "retries": 3,
    "extractor_retries": 3,
    "fragment_retries": 5,
    # Realistic browser headers to reduce rate-limiting
    "http_headers": {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    },
}


class DownloadError(Exception):
    pass


class YtDlpDownloader(BaseDownloader):
    """yt-dlp based downloader for public YouTube videos."""

    @property
    def name(self) -> str:
        return "yt-dlp"

    def _build_ydl_opts(self, option: str, file_id: str, output_directory: str) -> dict:
        opts = dict(_BASE_OPTS)
        downloads_path = Path(output_directory)

        if option == "mp3":
            # Use %(ext)s — yt-dlp will rename to .mp3 after FFmpegExtractAudio
            opts["outtmpl"] = str(downloads_path / f"{file_id}.%(ext)s")
            opts.update({
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            })
        else:
            # Use %(ext)s so yt-dlp handles extension correctly after merge
            opts["outtmpl"] = str(downloads_path / f"{file_id}.%(ext)s")
            opts.update({
                "format": FORMAT_MAP[option],
                "merge_output_format": "mp4",
            })

        return opts

    def _extract_info_sync(self, url: str) -> dict:
        """
        Extract video metadata without downloading. Used for /api/info.
        Returns a safe dict of metadata for caching and frontend display.
        """
        opts = dict(_BASE_OPTS)
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            raise DownloadError("Could not extract video metadata")

        # Build a safe, cacheable metadata dict
        thumbnail = None
        thumbnails = info.get("thumbnails") or []
        # Pick highest quality thumbnail
        if thumbnails:
            best = max(thumbnails, key=lambda t: (t.get("width") or 0) * (t.get("height") or 0))
            thumbnail = best.get("url")
        if not thumbnail:
            thumbnail = info.get("thumbnail")

        return {
            "title": info.get("title", "Unknown video"),
            "uploader": info.get("uploader") or info.get("channel", ""),
            "duration": info.get("duration"),
            "view_count": info.get("view_count"),
            "like_count": info.get("like_count"),
            "thumbnail": thumbnail,
            "webpage_url": info.get("webpage_url", url),
            "upload_date": info.get("upload_date"),
            "description": (info.get("description") or "")[:200],
        }

    async def extract_info(self, url: str) -> dict:
        """Async wrapper for metadata-only extraction."""
        return await asyncio.to_thread(self._extract_info_sync, url)

    def _download_sync(self, url: str, output_directory: str, option: str) -> DownloadResult:
        file_id = str(uuid.uuid4())
        downloads_path = Path(output_directory)
        downloads_path.mkdir(parents=True, exist_ok=True)

        ydl_opts = self._build_ydl_opts(option, file_id, output_directory)

        retries = 0
        last_error = None

        while retries <= settings.max_retries:
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    title = info.get("title", "Unknown video") if info else "Unknown video"

                # Find the output file — yt-dlp names it with the actual ext
                expected_ext = "mp3" if option == "mp3" else "mp4"
                expected_path = downloads_path / f"{file_id}.{expected_ext}"

                if not expected_path.exists():
                    # Fallback: glob for any file with our UUID stem
                    for candidate in downloads_path.glob(f"{file_id}.*"):
                        suf = candidate.suffix.lower()
                        if suf in (".mp4", ".mp3"):
                            expected_path = candidate
                            break

                if not expected_path.exists():
                    raise DownloadError("Output file was not created")

                final_ext = expected_path.suffix.lower().lstrip(".")
                if final_ext not in ("mp4", "mp3"):
                    raise DownloadError(f"Unexpected file extension: {final_ext}")

                final_filename = expected_path.name
                file_size = expected_path.stat().st_size
                file_size_str = _format_size(file_size)

                quality_selected = option
                if option != "mp3" and info:
                    height = info.get("height")
                    if height and height < QUALITY_HEIGHTS.get(option, 0):
                        quality_selected = f"{height}p"

                return DownloadResult(
                    title=title,
                    filename=final_filename,
                    option_requested=option,
                    quality_selected=quality_selected,
                    downloader_used=self.name,
                    download_url=f"/api/file/{final_filename}",
                    file_size=file_size_str,
                )

            except yt_dlp.utils.DownloadError as e:
                last_error = e
                retries += 1
                if retries <= settings.max_retries:
                    logger.warning(f"Download attempt {retries} failed, retrying... {e}")
                else:
                    break
            except Exception as e:
                last_error = e
                retries += 1
                if retries <= settings.max_retries:
                    logger.warning(f"Download attempt {retries} failed, retrying... {e}")
                else:
                    break

        raise DownloadError(f"Download failed after {retries} attempts") from last_error

    async def download(self, url: str, output_directory: str, option: str) -> DownloadResult:
        return await asyncio.to_thread(
            self._download_sync, url, output_directory, option
        )


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
