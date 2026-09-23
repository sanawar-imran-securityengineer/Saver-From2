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
import json
import logging
import shutil
import subprocess
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


def ffprobe_available() -> bool:
    """True when ffprobe is reachable so we can validate the final media file."""
    if settings.FFMPEG_LOCATION:
        ffprobe_path = Path(settings.FFMPEG_LOCATION)
        if ffprobe_path.is_dir():
            for candidate in (ffprobe_path / "ffprobe", ffprobe_path / "ffprobe.exe"):
                if candidate.exists():
                    return True
            return False
        return ffprobe_path.exists() and ffprobe_path.name.lower().startswith("ffprobe")
    return bool(shutil.which("ffprobe"))


class YtDlpDownloader:
    """yt-dlp based downloader that writes a real file into the downloads dir."""

    name = "yt-dlp"

    def base_opts(self, spec: Optional[PlatformSpec] = None) -> Dict[str, Any]:
        from .ytdlp import ydl_base_opts

        opts = ydl_base_opts(spec)
        opts["skip_download"] = False
        opts["restrictfilenames"] = True
        opts["retries"] = 0               # yt-dlp internal retries off; our loop handles it
        opts["extractor_retries"] = 1
        opts["fragment_retries"] = 2       # minimal fragment retries — fail fast
        opts["http_chunk_size"] = 20971520 # 20 MB chunks — fewer requests, faster on large files

        # Per-platform speed tuning ───────────────────────────────────────────
        _key = spec.key if spec else ""
        if _key == "youtube":
            # YouTube HTTP-chunked downloads benefit from very high parallelism.
            opts["concurrent_fragment_downloads"] = 128
            opts["buffersize"] = 33554432   # 32 MB
            opts["socket_timeout"] = 8
        elif _key in ("instagram", "facebook", "threads"):
            # DASH / separate a+v streams → max parallel segment downloads
            opts["concurrent_fragment_downloads"] = 128
            opts["buffersize"] = 33554432
            opts["socket_timeout"] = 15
            if _key == "instagram":
                opts["http_chunk_size"] = 1048576  # 1 MB chunks to force concurrent HTTP downloading
        elif _key == "reddit":
            # v.redd.it DASH — parallel segments for speed
            opts["concurrent_fragment_downloads"] = 128
            opts["buffersize"] = 33554432
            opts["socket_timeout"] = 12
        elif _key == "pinterest":
            opts["concurrent_fragment_downloads"] = 128
            opts["buffersize"] = 33554432
            opts["socket_timeout"] = 12
        elif _key == "twitch":
            # HLS live/VOD — max workers for wall-clock speed
            opts["concurrent_fragment_downloads"] = 64
            opts["socket_timeout"] = 15
        elif _key == "twitter":
            opts["concurrent_fragment_downloads"] = 64
            opts["socket_timeout"] = 15
        elif _key == "snapchat":
            opts["concurrent_fragment_downloads"] = 64
            opts["socket_timeout"] = 15
        else:
            opts["concurrent_fragment_downloads"] = 64
            opts["socket_timeout"] = 15

        if settings.FFMPEG_LOCATION:
            opts["ffmpeg_location"] = settings.FFMPEG_LOCATION

        # Use aria2c if available for faster downloading
        if shutil.which("aria2c"):
            opts["external_downloader"] = "aria2c"
            opts["external_downloader_args"] = {"aria2c": ["-x", "16", "-s", "16", "-k", "1M"]}

        return opts

    def _prefer_audio_video_merge(self, spec: Optional[PlatformSpec], option: str) -> str:
        if option == "mp3":
            return "bestaudio/best"

        # Platforms that always deliver separate video+audio streams — we must
        # tell yt-dlp to merge them with FFmpeg, otherwise we get video-only.
        if spec is not None and spec.key in ("instagram", "facebook", "reddit", "threads", "pinterest"):
            # Very broad selector: try mp4+m4a first, then any video+audio combo, then anything
            return (
                "bestvideo[ext=mp4]+bestaudio[ext=m4a]"
                "/bestvideo[ext=mp4]+bestaudio"
                "/bestvideo+bestaudio[ext=m4a]"
                "/bestvideo+bestaudio"
                "/best[ext=mp4]/best"
            )

        return FORMAT_MAP.get(option, FORMAT_MAP["best"])

    def validate_media_file(self, path: Path, option: str, spec: Optional[PlatformSpec] = None) -> None:
        if not path.exists() or path.stat().st_size <= 1024:
            raise DownloadError("The downloaded file is empty or missing.")

        if path.suffix.lower() == ".mp3" or option == "mp3":
            return

        if spec is not None and spec.key == "instagram" and not ffmpeg_available():
            raise DownloadError(
                "Instagram downloads require FFmpeg so the final video keeps the original background audio."
            )

        probe = shutil.which("ffprobe")
        if settings.FFMPEG_LOCATION:
            ffmpeg_dir = Path(settings.FFMPEG_LOCATION)
            if ffmpeg_dir.is_dir():
                for candidate in (ffmpeg_dir / "ffprobe", ffmpeg_dir / "ffprobe.exe"):
                    if candidate.exists():
                        probe = str(candidate)
                        break
            elif ffmpeg_dir.name.lower().startswith("ffprobe") and ffmpeg_dir.exists():
                probe = str(ffmpeg_dir)

        if not probe:
            return

        cmd = [str(probe), "-v", "error", "-show_streams", "-of", "json", str(path)]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as exc:
            raise DownloadError("The downloaded file could not be validated.") from exc

        if proc.returncode != 0:
            raise DownloadError("The downloaded video file is corrupted or unreadable.")

        try:
            payload = json.loads(proc.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise DownloadError("The downloaded video file failed media validation.") from exc

        streams = payload.get("streams") or []
        video_streams = [s for s in streams if s.get("codec_type") == "video"]
        if not video_streams:
            raise DownloadError("The downloaded file does not contain a valid video stream.")

        # Pinterest clips often embed audio inside the video track or are silent —
        # do not require a separate audio stream for them.
        if spec is not None and spec.key in ("instagram", "facebook", "reddit", "threads"):
            audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
            if not audio_streams:
                raise DownloadError(
                    "The video was downloaded but the audio track is missing. "
                    "Please try again — if this keeps happening, FFmpeg may not have "
                    "enough permissions to merge the streams."
                )

    def build_opts(
        self,
        option: str,
        file_id: str,
        output_directory: Path,
        spec: Optional[PlatformSpec] = None,
    ) -> Dict[str, Any]:
        opts = self.base_opts(spec)
        opts["outtmpl"] = str(Path(output_directory) / f"{file_id}.%(ext)s")

        if option == "mp3":
            audio_fmt = "bestaudio[ext=m4a]/bestaudio/best"
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
            _key = spec.key if spec else ""

            if _key == "youtube":
                # Quality-aware YouTube selector using itags AND height caps.
                # itag 22 = 720p mp4, itag 18 = 360p mp4 (both progressive, no merge needed).
                # For higher quality we allow merging.
                _h = QUALITY_HEIGHTS.get(option, 0)
                if _h >= 1080:
                    opts["format"] = (
                        f"bestvideo[height<={_h}][ext=mp4]+bestaudio[ext=m4a]"
                        f"/bestvideo[height<={_h}]+bestaudio"
                        "/22/18/b[ext=mp4]/b"
                    )
                    opts["merge_output_format"] = "mp4"
                elif _h >= 720:
                    opts["format"] = "22/bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/18/b[ext=mp4]/b"
                    opts["merge_output_format"] = "mp4"
                else:
                    # 360p / 480p — always progressive, no ffmpeg needed
                    opts["format"] = "18/b[ext=mp4]/b"

            elif _key in ("facebook", "threads", "instagram"):
                if _key == "instagram":
                    # Instagram usually has a single pre-merged file. Prefer it to bypass FFmpeg entirely.
                    opts["format"] = "b[ext=mp4]/b/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best"
                    opts["merge_output_format"] = "mp4"
                    opts["prefer_ffmpeg"] = True
                    opts["postprocessor_args"] = {
                        "merger": ["-c:v", "copy", "-c:a", "copy"],
                    }
                else:
                    # Facebook/Threads: always DASH — use broadest fallback chain.
                    # CRITICAL: prefer_ffmpeg + postprocessor_args forces FFmpeg to always merge
                    # the separate video+audio streams so the final mp4 has audio.
                    opts["format"] = (
                        "bestvideo[ext=mp4]+bestaudio[ext=m4a]"
                        "/bestvideo[ext=mp4]+bestaudio"
                        "/bestvideo+bestaudio[ext=m4a]"
                        "/bestvideo+bestaudio/best"
                    )
                    opts["merge_output_format"] = "mp4"
                    opts["prefer_ffmpeg"] = True
                    opts["postprocessor_args"] = {
                        "merger": ["-c:v", "copy", "-c:a", "aac"],
                    }

            elif _key == "reddit":
                # v.redd.it DASH — must merge video+audio
                opts["format"] = (
                    "bestvideo[ext=mp4]+bestaudio[ext=m4a]"
                    "/bestvideo[ext=mp4]+bestaudio"
                    "/bestvideo+bestaudio/best"
                )
                opts["merge_output_format"] = "mp4"

            elif _key == "pinterest":
                # Pinterest CDN: very broad selector with explicit fallbacks.
                # Some pins have only a single MP4 stream (no separate audio) so
                # we must fall through all the way to the bare 'best' selector.
                opts["format"] = (
                    "bestvideo[ext=mp4]+bestaudio[ext=m4a]"
                    "/bestvideo[ext=mp4]+bestaudio"
                    "/bestvideo+bestaudio"
                    "/best[ext=mp4]"
                    "/best"
                    "/bestvideo[ext=mp4]"
                    "/bestvideo"
                    "/b"
                )
                # Attempt a merge; if only one stream exists yt-dlp ignores it.
                opts["merge_output_format"] = "mp4"
                # Do NOT validate audio stream for Pinterest — many clips are
                # silent or have audio baked in to the video track.
                opts["_pinterest_no_audio_check"] = True

            else:
                fmt = self._prefer_audio_video_merge(spec, option)
                opts["format"] = fmt
                opts["merge_output_format"] = "mp4"

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
        if spec is not None and spec.key == "instagram" and option != "mp3" and not ffmpeg_available():
            raise DownloadError(
                "Instagram downloads require FFmpeg so the final video keeps the original background audio."
            )
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

                # Validate the final media file (ffprobe) before reporting success.
                try:
                    self.validate_media_file(expected_path, option, spec)
                except DownloadError:
                    # Remove invalid output to avoid serving corrupted/silent files.
                    try:
                        expected_path.unlink()
                    except Exception:
                        pass
                    raise

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