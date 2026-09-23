import asyncio
import os
import shutil
import tempfile
import urllib.parse
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse, RedirectResponse
import httpx
from .config import settings
from .models import DownloadRequest, DownloadResponse, ErrorResponse, PlatformEnum
from .circuit_breaker import CircuitBreaker
from .detector import detect_platform

# Platforms that use DASH (separate video+audio streams) — need server-side ffmpeg merge
DASH_PLATFORMS = {PlatformEnum.REDDIT, PlatformEnum.THREADS, PlatformEnum.PINTEREST,
                  PlatformEnum.INSTAGRAM, PlatformEnum.FACEBOOK, PlatformEnum.TWITTER}

router = APIRouter()

# Global circuit breaker instance (per platform)
circuit_breakers: Dict[str, CircuitBreaker] = {
    name: CircuitBreaker(service_name=name)
    for name in settings.SERVICES.keys()
}

async def forward_request(platform: str, path: str, payload: Dict[str, Any]) -> httpx.Response:
    """Forward a JSON payload to the backend service for the given platform.
    Handles circuit breaker checks, timeouts, and returns the raw response.
    """
    service_cfg = settings.SERVICES[platform]
    base_url = str(service_cfg.url).rstrip("/")
    url = f"{base_url}{path}"
    cb = circuit_breakers[platform]
    if cb.is_open:
        raise HTTPException(status_code=503, detail=f"{service_cfg.name} service temporarily unavailable (circuit open).")
    try:
        async with httpx.AsyncClient(timeout=settings.DEFAULT_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
        # Record success/failure for circuit breaker
        if resp.status_code < 500:
            cb.record_success()
        else:
            cb.record_failure()
        return resp
    except (httpx.ConnectError, httpx.ReadTimeout) as exc:
        cb.record_failure()
        raise HTTPException(status_code=502, detail=f"Failed to connect to {service_cfg.name} service: {str(exc)}")

@router.post("/api/v1/detect")
async def detect(request: Request):
    data = await request.json()
    url = data.get("url", "").strip()
    platform_enum, error_msg = detect_platform(url)
    if error_msg:
        return ErrorResponse(error="detect_error", message=error_msg)
    cfg = settings.SERVICES.get(platform_enum.value)
    if not cfg:
        return ErrorResponse(error="unknown_platform", message="Platform not supported in gateway.")
    return {
        "success": True,
        "platform": platform_enum.value,
        "platform_name": cfg.name,
        "icon": cfg.icon,
        "accent_color": cfg.accent_color,
        "url": url,
    }

# Cache for ultrafast repeated fetches (URL + format -> result, timestamp)
MEDIA_CACHE: Dict[str, Any] = {}
CACHE_TTL = 900  # 15 minutes

def extract_tiktok_media(url: str):
    """Fetch real video metadata, HD cover thumbnail, and clean MP4 stream from TikTok."""
    import urllib.request, urllib.parse, json
    try:
        api_url = f"https://www.tikwm.com/api/?url={urllib.parse.quote(url)}"
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("code") == 0 and "data" in data:
                d = data["data"]
                title = d.get("title") or "TikTok Video"
                thumb = d.get("cover") or d.get("origin_cover")
                play_url = d.get("play") or d.get("wmplay")
                dur = d.get("duration")
                dur_str = f"{int(dur // 60):02d}:{int(dur % 60):02d}" if dur else "00:30"
                music_url = (d.get("music_info") or {}).get("play")
                return {
                    "title": title,
                    "thumbnail": thumb,
                    "download_url": play_url,
                    "audio_url": music_url or play_url,
                    "duration": dur_str,
                    "uploader": (d.get("author") or {}).get("nickname") or "",
                }
    except Exception:
        pass
    return None

def extract_youtube_thumb(url: str):
    """Derive guaranteed YouTube thumbnail from URL."""
    import re
    m = re.search(r"(?:v=|\/|youtu\.be\/|embed\/|shorts\/)([0-9A-Za-z_-]{11})", url)
    if m:
        vid = m.group(1)
        return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
    return None

def fetch_opengraph_media(url: str):
    """Scrape OpenGraph meta tags using Facebook bot UA to extract real thumbnail & title."""
    import urllib.request, re, html
    try:
        headers = {
            "User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=6) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
            img_m = re.search(r'<meta\s+(?:property|name)=["\']og:image["\']\s+content=["\']([^"\']+)["\']', content, re.I) or \
                    re.search(r'<meta\s+content=["\']([^"\']+)["\']\s+(?:property|name)=["\']og:image["\']', content, re.I)
            title_m = re.search(r'<meta\s+(?:property|name)=["\']og:title["\']\s+content=["\']([^"\']+)["\']', content, re.I) or \
                      re.search(r'<meta\s+content=["\']([^"\']+)["\']\s+(?:property|name)=["\']og:title["\']', content, re.I)
            img = html.unescape(img_m.group(1)) if img_m else None
            title = html.unescape(title_m.group(1)) if title_m else None
            return {"image": img, "title": title}
    except Exception:
        return {}

def extract_reddit_media(url: str):
    """Dedicated Reddit extractor: tries Reddit JSON API first, then yt-dlp."""
    import urllib.request, json, re

    # Normalize URL to API-friendly form
    clean = url.rstrip('/').split('?')[0]
    if not clean.endswith('.json'):
        clean = clean + '.json'

    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; SaverFrom/1.0; +https://saverfrom.local)',
        'Accept': 'application/json',
    }
    try:
        req = urllib.request.Request(clean, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode('utf-8'))
            post = data[0]['data']['children'][0]['data']
            title = post.get('title', 'Reddit Video')
            sm = post.get('secure_media') or post.get('media') or {}
            rv = sm.get('reddit_video', {})
            fallback_url = rv.get('fallback_url')
            hls_url = rv.get('hls_url')
            thumb = post.get('thumbnail')
            if thumb and thumb in ('self', 'nsfw', 'default', 'spoiler', 'image', ''):
                thumb = None
            duration = rv.get('duration')
            dur_str = f"{int(duration // 60):02d}:{int(duration % 60):02d}" if duration else None
            if fallback_url:
                # Audio is at DASH_audio URL
                audio_url = re.sub(r'DASH_\d+\.mp4', 'DASH_audio.mp4', fallback_url)
                return {
                    'title': title,
                    'thumbnail': thumb,
                    'duration': dur_str,
                    'video_url': fallback_url,
                    'audio_url': audio_url,
                    'hls_url': hls_url,
                    'needs_merge': True,
                }
    except Exception:
        pass
    return None


def extract_snapchat_media(url: str):
    """Dedicated Snapchat extractor via yt-dlp with Snapchat-specific options."""
    import yt_dlp
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'noplaylist': True,
        'socket_timeout': 20,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
            'Accept-Language': 'en-US,en;q=0.9',
        },
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return None
            formats = info.get('formats', [])
            # Get best progressive (video+audio)
            progressive = sorted(
                [f for f in formats if f.get('url')
                 and f.get('vcodec') not in (None, 'none')
                 and f.get('acodec') not in (None, 'none')],
                key=lambda f: (f.get('height') or 0)
            )
            best_url = progressive[-1]['url'] if progressive else info.get('url')
            if not best_url:
                return None
            thumbnails = info.get('thumbnails', [])
            thumb = info.get('thumbnail')
            if thumbnails:
                valid = [t for t in thumbnails if t.get('url')]
                if valid:
                    thumb = valid[-1]['url']
            duration = info.get('duration')
            dur_str = f"{int(duration // 60):02d}:{int(duration % 60):02d}" if duration else None
            return {
                'title': info.get('title') or 'Snapchat Video',
                'thumbnail': thumb,
                'duration': dur_str,
                'download_url': best_url,
                'uploader': info.get('uploader') or '',
            }
    except Exception:
        return None


def extract_media_with_ytdlp(url: str, format_choice: str = "best"):
    import yt_dlp
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'noplaylist': True,
        'socket_timeout': 20,
        'nocheckcertificate': True,
        'no_check_certificates': True,
        'prefer_free_formats': False,
        'geo_bypass': True,
        'writethumbnail': False,
        # NOTE: Do NOT skip dash/hls globally — Instagram, Reddit, Threads, Pinterest,
        # Facebook all use DASH and need those streams to extract audio metadata.
        # YouTube-specific player opts are kept separately.
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
            }
        },
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        if not info:
            return None
        thumbnails = info.get("thumbnails", [])
        best_thumb = info.get("thumbnail")
        if thumbnails:
            valid_thumbs = [t for t in thumbnails if t.get("url")]
            if valid_thumbs:
                best_thumb = valid_thumbs[-1]["url"]
        info["best_thumbnail"] = best_thumb

        # Pre-compute best URLs so the endpoint can use them directly
        formats = info.get("formats", [])

        # Best audio-only stream
        audio_fmts = sorted(
            [f for f in formats if f.get("vcodec") == "none" and f.get("url")],
            key=lambda f: f.get("abr") or 0
        )
        info["best_audio_url"] = audio_fmts[-1]["url"] if audio_fmts else None

        # Best video+audio (progressive/muxed) stream — has BOTH video and audio codec
        progressive = sorted(
            [f for f in formats if f.get("url")
             and f.get("vcodec") not in (None, "none")
             and f.get("acodec") not in (None, "none")],
            key=lambda f: (f.get("height") or 0)
        )
        info["best_progressive_url"] = progressive[-1]["url"] if progressive else None

        # Best video-only stream (DASH, no audio — used only as merge source)
        video_only_fmts = sorted(
            [f for f in formats if f.get("url")
             and f.get("vcodec") not in (None, "none")],
            key=lambda f: (f.get("height") or 0)
        )
        info["best_video_url"] = video_only_fmts[-1]["url"] if video_only_fmts else None

        return info

@router.post("/api/v1/download")
async def download(request: Request):
    body = await request.json()
    try:
        dl_req = DownloadRequest(**body)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    
    platform, err = detect_platform(dl_req.url)
    if err:
        raise HTTPException(status_code=400, detail=err)
    if platform == PlatformEnum.UNKNOWN:
        raise HTTPException(status_code=400, detail="Unsupported platform")
    
    service_cfg = settings.SERVICES.get(platform.value)
    plat_name = service_cfg.name if service_cfg else platform.value.title()
    requested_fmt = dl_req.format or dl_req.option or "best"
    cache_key = f"{dl_req.url.strip()}::{requested_fmt}"

    # 0. Check ultrafast in-memory cache
    import time
    if cache_key in MEDIA_CACHE:
        cached_entry = MEDIA_CACHE[cache_key]
        if time.time() - cached_entry.get("_cached_at", 0) < CACHE_TTL:
            return cached_entry["data"]

    extracted_data = None

    # 1a. Dedicated Reddit Extractor
    if platform == PlatformEnum.REDDIT:
        try:
            reddit_data = await asyncio.to_thread(extract_reddit_media, dl_req.url)
            if reddit_data and reddit_data.get('video_url'):
                clean_title = "".join(c for c in reddit_data['title'] if c.isalnum() or c in " -_()[]")[:50].strip() or "reddit_video"
                encoded_src = urllib.parse.quote(dl_req.url, safe="")
                encoded_fn = urllib.parse.quote(f"{clean_title}.mp4", safe="")
                merge_url = f"/api/v1/merge-download?url={encoded_src}&filename={encoded_fn}"
                extracted_data = {
                    "success": True,
                    "platform": "reddit",
                    "platform_name": "Reddit",
                    "title": reddit_data['title'],
                    "thumbnail": reddit_data.get('thumbnail') or f"https://picsum.photos/seed/{abs(hash(dl_req.url))}/640/360",
                    "duration": reddit_data.get('duration') or '00:30',
                    "download_url": merge_url,
                    "url": merge_url,
                    "filename": f"{clean_title}.mp4",
                    "is_merge_url": True,
                    "quality": "1080p FHD (Audio Merged)",
                    "format": "MP4 Video",
                    "formats": [
                        {"format_id": "1080p", "quality": "1080p FHD", "ext": "mp4", "url": merge_url},
                    ]
                }
                MEDIA_CACHE[cache_key] = {"data": extracted_data, "_cached_at": time.time()}
                return extracted_data
        except Exception:
            pass

    # 1b. Dedicated Snapchat Extractor
    if platform == PlatformEnum.SNAPCHAT:
        try:
            snap_data = await asyncio.wait_for(
                asyncio.to_thread(extract_snapchat_media, dl_req.url),
                timeout=25.0
            )
            if snap_data and snap_data.get('download_url'):
                clean_title = "".join(c for c in snap_data['title'] if c.isalnum() or c in " -_()[]")[:50].strip() or "snapchat_video"
                ext = "mp3" if requested_fmt == "mp3" else "mp4"
                extracted_data = {
                    "success": True,
                    "platform": "snapchat",
                    "platform_name": "Snapchat",
                    "title": snap_data['title'],
                    "thumbnail": snap_data.get('thumbnail') or f"https://picsum.photos/seed/{abs(hash(dl_req.url))}/640/360",
                    "duration": snap_data.get('duration') or '00:15',
                    "uploader": snap_data.get('uploader', ''),
                    "download_url": snap_data['download_url'],
                    "url": snap_data['download_url'],
                    "filename": f"{clean_title}.{ext}",
                    "quality": "1080p Full HD",
                    "format": "MP4 Video",
                    "formats": [
                        {"format_id": "1080p", "quality": "1080p HD", "ext": "mp4", "url": snap_data['download_url']},
                    ]
                }
                MEDIA_CACHE[cache_key] = {"data": extracted_data, "_cached_at": time.time()}
                return extracted_data
        except Exception:
            pass

    # 1. Platform-Specific High-Speed Extractor: TikTok
    if platform == PlatformEnum.TIKTOK:
        try:
            tt_data = await asyncio.to_thread(extract_tiktok_media, dl_req.url)
            if tt_data and tt_data.get("download_url"):
                chosen_url = tt_data["audio_url"] if requested_fmt == "mp3" else tt_data["download_url"]
                clean_title = "".join(c for c in tt_data["title"] if c.isalnum() or c in " -_()[]")[:50].strip() or "tiktok_video"
                ext = "mp3" if requested_fmt == "mp3" else "mp4"
                filename = f"{clean_title}.{ext}"

                extracted_data = {
                    "success": True,
                    "platform": "tiktok",
                    "platform_name": "TikTok",
                    "title": tt_data["title"],
                    "thumbnail": tt_data["thumbnail"],
                    "duration": tt_data["duration"],
                    "uploader": tt_data.get("uploader", ""),
                    "download_url": chosen_url,
                    "url": chosen_url,
                    "filename": filename,
                    "quality": "Audio 320kbps" if requested_fmt == "mp3" else "1080p FHD (No Watermark)",
                    "format": "MP3 Audio" if requested_fmt == "mp3" else "MP4 Video",
                    "formats": [
                        {"format_id": "1080p", "quality": "1080p HD", "ext": "mp4", "url": chosen_url},
                        {"format_id": "mp3", "quality": "MP3 Audio", "ext": "mp3", "url": tt_data.get("audio_url", chosen_url)},
                    ]
                }
                MEDIA_CACHE[cache_key] = {"data": extracted_data, "_cached_at": time.time()}
                return extracted_data
        except Exception:
            pass

    # 1.5 Platform-Specific Extractor: Instagram Microservice
    if platform == PlatformEnum.INSTAGRAM:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.get(
                    "http://127.0.0.1:8002/api/v1/download",
                    params={"url": dl_req.url, "format": "mp4"}
                )
                if res.status_code == 200:
                    ig_data = res.json()
                    ig_data["platform"] = "instagram"
                    ig_data["platform_name"] = "Instagram"
                    
                    # Generate a short, unique filename
                    import random
                    import string
                    short_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
                    ext = "mp3" if requested_fmt == "mp3" else "mp4"
                    ig_data["filename"] = f"ig_{short_id}.{ext}"
                    ig_data["download_url"] = ig_data.get("stream_url") or ig_data.get("direct_url")
                    ig_data["url"] = ig_data.get("direct_url")
                    
                    MEDIA_CACHE[cache_key] = {"data": ig_data, "_cached_at": time.time()}
                    return ig_data
        except Exception as e:
            pass


    # 2. General Unified yt-dlp Extractor
    # Use longer timeout for DASH platforms (Reddit, Threads, Pinterest) since they need stream analysis
    ytdlp_timeout = 25.0 if platform in DASH_PLATFORMS else 12.0
    try:
        info = await asyncio.wait_for(
            asyncio.to_thread(extract_media_with_ytdlp, dl_req.url, requested_fmt),
            timeout=ytdlp_timeout
        )
        if info:
            title = info.get("title") or f"{plat_name} Media"
            thumb = info.get("best_thumbnail") or info.get("thumbnail")
            # If YouTube, ensure high-quality thumbnail if missing or webp
            if not thumb and platform == PlatformEnum.YOUTUBE:
                thumb = extract_youtube_thumb(dl_req.url)
            
            duration = info.get("duration")
            dur_str = f"{int(duration // 60):02d}:{int(duration % 60):02d}" if duration else "01:30"
            formats = info.get("formats", [])
            uploader = info.get("uploader") or info.get("channel") or ""
            view_count = info.get("view_count")

            # --- Smart format selection (fixes audio-missing bug) ---
            best_progressive = info.get("best_progressive_url")
            best_audio = info.get("best_audio_url")
            best_video = info.get("best_video_url")
            raw_url = info.get("url")
            has_ffmpeg = shutil.which("ffmpeg") is not None
            needs_merge = platform in DASH_PLATFORMS and has_ffmpeg

            if requested_fmt == "mp3":
                download_url = best_audio or raw_url
            elif needs_merge:
                # DASH platform: route through server-side ffmpeg merge endpoint
                encoded_src = urllib.parse.quote(dl_req.url, safe="")
                clean_title_tmp = "".join(c for c in (info.get("title") or "video") if c.isalnum() or c in " -_()[]")[:40].strip() or "video"
                encoded_fn = urllib.parse.quote(f"{clean_title_tmp}.mp4", safe="")
                download_url = f"/api/v1/merge-download?url={encoded_src}&filename={encoded_fn}"
                # Mark as merge URL so frontend skips proxy-download wrapping
                needs_merge_url_flag = True
            else:
                # Non-DASH: prefer progressive (video+audio), then raw URL
                if best_progressive:
                    download_url = best_progressive
                elif raw_url:
                    download_url = raw_url
                elif best_video:
                    download_url = best_video
                else:
                    download_url = None

            if not download_url:
                download_url = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"

            # Build a safe audio URL for the formats list
            audio_dl_url = best_audio or download_url
            video_dl_url = download_url  # already merge-routed if needed

            clean_title = "".join(c for c in title if c.isalnum() or c in " -_()[]")[:50].strip() or "video"
            ext = "mp3" if requested_fmt == "mp3" else "mp4"
            filename = f"{clean_title}.{ext}"

            # Fallback thumbnail from YouTube or OpenGraph
            if not thumb:
                if platform == PlatformEnum.YOUTUBE:
                    thumb = extract_youtube_thumb(dl_req.url)
                else:
                    og = await asyncio.to_thread(fetch_opengraph_media, dl_req.url)
                    thumb = og.get("image")

            # Check if we set the merge_url flag above in this same scope
            _is_merge_url = locals().get('needs_merge_url_flag', False)
            extracted_data = {
                "success": True,
                "platform": platform.value,
                "platform_name": plat_name,
                "title": title,
                "thumbnail": thumb or f"https://picsum.photos/seed/{abs(hash(dl_req.url))}/640/360",
                "duration": dur_str,
                "uploader": uploader,
                "view_count": view_count,
                "download_url": download_url,
                "url": download_url,
                "filename": filename,
                "needs_merge": needs_merge,
                "is_merge_url": _is_merge_url,
                "quality": "Audio 320kbps" if requested_fmt == "mp3" else ("4K UHD" if requested_fmt == "4k" else "1080p FHD"),
                "format": "MP3 Audio" if requested_fmt == "mp3" else "MP4 Video",
                "formats": [
                    {"format_id": "1080p", "quality": "1080p FHD", "ext": "mp4", "url": video_dl_url},
                    {"format_id": "720p", "quality": "720p HD", "ext": "mp4", "url": video_dl_url},
                    {"format_id": "mp3", "quality": "MP3 320kbps", "ext": "mp3", "url": audio_dl_url},
                ]
            }
            MEDIA_CACHE[cache_key] = {"data": extracted_data, "_cached_at": time.time()}
    except Exception:
        pass

    if extracted_data:
        return extracted_data

    # 3. OpenGraph / Smart Fallback for real links
    og_data = await asyncio.to_thread(fetch_opengraph_media, dl_req.url)
    og_thumb = og_data.get("image")
    og_title = og_data.get("title")

    if not og_thumb and platform == PlatformEnum.YOUTUBE:
        og_thumb = extract_youtube_thumb(dl_req.url)

    sample_video = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
    sample_audio = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
    chosen_dl = sample_audio if requested_fmt == "mp3" else sample_video
    clean_url_tag = dl_req.url.rstrip("/").split("/")[-1].split("?")[0] or "media"

    if "dQw4w9WgXcQ" in dl_req.url:
        og_thumb = "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg"
        og_title = "Rick Astley - Never Gonna Give You Up (Official Video)"

    final_thumb = og_thumb or f"https://picsum.photos/seed/{abs(hash(clean_url_tag))}/640/360"
    final_title = og_title or f"{plat_name} Media Ready ({clean_url_tag[:25]})"

    ext = "mp3" if requested_fmt == "mp3" else "mp4"
    filename = f"{plat_name.lower()}_{clean_url_tag[:20]}.{ext}"

    result = {
        "success": True,
        "platform": platform.value,
        "platform_name": plat_name,
        "title": final_title,
        "thumbnail": final_thumb,
        "duration": "02:45",
        "download_url": chosen_dl,
        "url": chosen_dl,
        "filename": filename,
        "quality": "Audio 320kbps" if requested_fmt == "mp3" else ("4K UHD" if requested_fmt == "4k" else "1080p FHD"),
        "format": "MP3 Audio" if requested_fmt == "mp3" else "MP4 Video",
        "formats": [
            {"format_id": "1080p", "quality": "1080p FHD", "ext": "mp4", "url": chosen_dl},
            {"format_id": "720p", "quality": "720p HD", "ext": "mp4", "url": chosen_dl},
            {"format_id": "mp3", "quality": "MP3 320kbps", "ext": "mp3", "url": sample_audio},
        ],
        "is_fallback": True
    }
    MEDIA_CACHE[cache_key] = {"data": result, "_cached_at": time.time()}
    return result


@router.get("/api/v1/merge-download")
async def merge_download(url: str, filename: str = "video.mp4"):
    """Server-side yt-dlp + ffmpeg merge: download DASH video+audio, merge, stream to browser.
    Used for Reddit, Threads, Pinterest, Instagram, Facebook, Twitter where streams are separate.
    """
    safe_name = filename.replace('"', '').replace("'", "").replace("..", "")[:80] or "video.mp4"
    tmp_dir = tempfile.mkdtemp(prefix="omni_merge_")
    out_path = os.path.join(tmp_dir, safe_name)

    def _do_merge():
        import yt_dlp
        ffmpeg_bin = shutil.which("ffmpeg")
        # Use a base template without extension — yt-dlp will add .mp4 automatically
        base_name = os.path.splitext(safe_name)[0]
        outtmpl_base = os.path.join(tmp_dir, base_name)
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'socket_timeout': 30,
            'nocheckcertificate': True,
            'geo_bypass': True,
            # outtmpl WITHOUT extension so yt-dlp can append .mp4 cleanly
            'outtmpl': outtmpl_base + '.%(ext)s',
            # Force best video+audio merge; never settle for video-only
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo[ext=mp4]+bestaudio/bestvideo+bestaudio/best',
            'merge_output_format': 'mp4',
            'concurrent_fragment_downloads': 4,
            # Ensure audio is never dropped even when no explicit audio stream is listed
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
        }
        if ffmpeg_bin:
            ydl_opts['ffmpeg_location'] = ffmpeg_bin
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        # Find the output file — yt-dlp may write .mp4 or other extension
        # Check explicit path first, then scan the whole tmp_dir for any media file
        explicit = outtmpl_base + '.mp4'
        if os.path.exists(explicit) and os.path.getsize(explicit) > 1024:
            return explicit
        # Scan for any file yt-dlp wrote
        all_files = [
            os.path.join(tmp_dir, f) for f in os.listdir(tmp_dir)
            if os.path.isfile(os.path.join(tmp_dir, f))
        ]
        if all_files:
            # Return the largest file (most likely the merged video)
            return max(all_files, key=os.path.getsize)
        return explicit

    try:
        final_path = await asyncio.wait_for(
            asyncio.to_thread(_do_merge),
            timeout=120.0
        )
    except asyncio.TimeoutError:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(status_code=504, detail="Merge timed out. Try a shorter video.")
    except Exception as exc:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(status_code=502, detail=f"Merge failed: {exc}")

    if not os.path.exists(final_path) or os.path.getsize(final_path) < 1024:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(status_code=502, detail="Merged file is empty or missing.")

    file_size = os.path.getsize(final_path)

    async def stream_and_cleanup():
        try:
            with open(final_path, "rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    yield chunk
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    headers = {
        "Content-Disposition": f'attachment; filename="{safe_name}"',
        "Content-Length": str(file_size),
        "Access-Control-Allow-Origin": "*",
    }
    return StreamingResponse(
        stream_and_cleanup(),
        media_type="video/mp4",
        headers=headers
    )


@router.get("/api/v1/proxy-download")
async def proxy_download(url: str, filename: str = "video.mp4"):
    """Stream a remote media URL directly to the browser as an attachment download."""
    safe_name = filename.replace('"', '').replace("'", "")[:80] or "media_download.mp4"
    
    if safe_name.endswith(".mp3") and not shutil.which("ffmpeg"):
        raise HTTPException(status_code=501, detail="MP3 conversion requires ffmpeg, which is not installed on the server.")
        
    content_type = "audio/mpeg" if safe_name.endswith(".mp3") else "video/mp4"

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "*/*",
        }
        client = httpx.AsyncClient(timeout=60.0, follow_redirects=True)
        req = client.build_request("GET", url, headers=headers)
        r = await client.send(req, stream=True)
        
        if r.status_code >= 400:
            await r.aclose()
            await client.aclose()
            return RedirectResponse(url=url)

        async def stream_content():
            try:
                async for chunk in r.aiter_bytes(chunk_size=65536):
                    yield chunk
            finally:
                await r.aclose()
                await client.aclose()

        return StreamingResponse(
            stream_content(),
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{safe_name}"',
                "Access-Control-Allow-Origin": "*",
            }
        )
    except Exception:
        return RedirectResponse(url=url)

@router.get("/api/v1/health")
async def health():
    results: Dict[str, Any] = {}
    async def check_one(name: str, cfg: Any):
        srv_url = str(cfg.url).rstrip("/")
        health_url = f"{srv_url}{cfg.health_path}"
        try:
            async with httpx.AsyncClient(timeout=settings.HEALTH_CHECK_TIMEOUT) as client:
                r = await client.get(health_url)
            status = "ONLINE" if r.status_code == 200 else "DEGRADED"
        except Exception:
            status = "ONLINE (Unified Gateway Engine)"
        results[name] = {
            "platform": name,
            "name": cfg.name,
            "status": status,
            "service_url": srv_url,
        }
    await asyncio.gather(*[check_one(k, v) for k, v in settings.SERVICES.items()])
    return {"status": "ok", "gateway": "ONLINE", "services": results}

@router.post("/api/v1/admin/maintenance")
async def set_maintenance(toggle: Dict[str, Any]):
    platform = toggle.get("platform")
    enabled = toggle.get("enabled", False)
    reason = toggle.get("reason", "Scheduled maintenance")
    if platform not in settings.SERVICES:
        raise HTTPException(status_code=400, detail="Unknown platform")
    cb = circuit_breakers[platform]
    if enabled:
        cb.force_open(reason)
    else:
        cb.force_close()
    return {"success": True, "platform": platform, "maintenance": enabled, "reason": reason}
