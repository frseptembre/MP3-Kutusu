"""MP3 Kutusu: tiny YouTube-to-MP3 application for authorized content."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import secrets
import shutil
import tempfile
import unicodedata
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yt_dlp
from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

ROOT = Path(__file__).resolve().parent
APP_KEY = os.getenv("APP_KEY", "")
MAX_DURATION_SECONDS = 60 * 60  # Limit resource usage on a small hosting plan.
MAX_SOURCE_BYTES = 180 * 1024 * 1024
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
CONVERT_LOCK = asyncio.Semaphore(1)
logger = logging.getLogger("mp3-kutusu")

app = FastAPI(title="MP3 Kutusu", docs_url=None, redoc_url=None, openapi_url=None)


class ConvertRequest(BaseModel):
    url: str = Field(min_length=1, max_length=500)


class FriendlyError(Exception):
    pass


def canonical_video_url(raw: str) -> str:
    """Restrict downloads to one ordinary YouTube video; never trust arbitrary URLs."""
    raw = raw.strip()
    try:
        parsed = urlparse(raw)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Geçerli bir YouTube video bağlantısı yapıştır.") from exc
    if parsed.scheme not in ("http", "https") or parsed.username or parsed.password or port is not None:
        raise ValueError("Geçerli bir YouTube video bağlantısı yapıştır.")

    host = (parsed.hostname or "").lower().rstrip(".")
    vid = None
    if host in {"www.youtube.com", "youtube.com", "m.youtube.com", "music.youtube.com"}:
        parts = [segment for segment in parsed.path.split("/") if segment]
        if parts == ["watch"]:
            vid = parse_qs(parsed.query).get("v", [None])[0]
        elif len(parts) == 2 and parts[0] in {"shorts", "live", "embed"}:
            vid = parts[1]
    elif host in {"youtu.be", "www.youtu.be"}:
        parts = [segment for segment in parsed.path.split("/") if segment]
        if len(parts) == 1:
            vid = parts[0]

    if not vid or not VIDEO_ID_RE.fullmatch(vid):
        raise ValueError("Yalnızca tek bir YouTube videosunun bağlantısını gir.")
    return f"https://www.youtube.com/watch?v={vid}"


def friendly_filename(title: str) -> str:
    title = unicodedata.normalize("NFC", title)
    title = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', "", title)
    title = re.sub(r"\s+", " ", title).strip(" .")[:90].rstrip(" .")
    if not title or title.upper() in {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "LPT1"}:
        title = "YouTube ses"
    return title + ".mp3"


def convert_video(url: str) -> tuple[Path, Path, str]:
    """Blocking yt-dlp operation; leaves artifacts to be removed after streaming."""
    temp_dir = Path(tempfile.mkdtemp(prefix="mp3-kutusu-"))
    try:
        opts = {
            "format": "bestaudio/best",
            "outtmpl": str(temp_dir / "%(id)s.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "retries": 2,
            "fragment_retries": 2,
            "socket_timeout": 20,
            "max_filesize": MAX_SOURCE_BYTES,
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"},
                {"key": "FFmpegMetadata"},
            ],
            # Deno and yt-dlp-ejs are installed by the Docker build.
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not isinstance(info, dict) or info.get("_type") == "playlist":
                raise FriendlyError("Bu bağlantı tek bir video olmalı.")
            duration = info.get("duration")
            if duration is None:
                raise FriendlyError("Bu videonun süresi belirlenemedi. Canlı yayınlar desteklenmiyor.")
            if duration > MAX_DURATION_SECONDS:
                raise FriendlyError("En fazla 60 dakikalık videolar dönüştürülebilir.")
            if info.get("is_live") or info.get("live_status") in {"is_live", "is_upcoming"}:
                raise FriendlyError("Canlı yayınlar dönüştürülemiyor.")
            # Run the conversion after checking duration, to bound server use.
            ydl.download([url])
            title = info.get("title") or "YouTube ses"

        mp3s = list(temp_dir.glob("*.mp3"))
        if len(mp3s) != 1 or mp3s[0].stat().st_size < 128:
            raise FriendlyError("MP3 oluşturulamadı. Başka bir video bağlantısı dene.")
        return temp_dir, mp3s[0], friendly_filename(str(title))
    except FriendlyError:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    except (yt_dlp.utils.DownloadError, yt_dlp.utils.ExtractorError, OSError) as exc:
        logger.warning("Download/conversion failure: %s", type(exc).__name__)
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise FriendlyError(
            "Video alınamadı. Video özel veya erişime kapalı olabilir ya da YouTube indirmeyi engellemiş olabilir."
        ) from exc
    except Exception:
        logger.exception("Unexpected conversion failure")
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise FriendlyError("Bir hata oluştu. Lütfen başka bir bağlantıyla tekrar dene.")


@app.middleware("http")
async def add_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; script-src 'self'; style-src 'self'; "
        "connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'self'"
    )
    return response


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(ROOT / "static" / "index.html", media_type="text/html; charset=utf-8")


@app.get("/styles.css", include_in_schema=False)
async def styles():
    return FileResponse(ROOT / "static" / "styles.css", media_type="text/css; charset=utf-8")


@app.get("/app.js", include_in_schema=False)
async def javascript():
    return FileResponse(ROOT / "static" / "app.js", media_type="text/javascript; charset=utf-8")


@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/api/convert")
async def convert(payload: ConvertRequest, request: Request):
    if APP_KEY and not secrets.compare_digest(request.headers.get("x-app-key", ""), APP_KEY):
        raise HTTPException(status_code=403, detail="Paylaşılan bağlantı eksik. Tam bağlantıyı iste.")
    try:
        url = canonical_video_url(payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if CONVERT_LOCK.locked():
        raise HTTPException(status_code=429, detail="Şu anda başka bir MP3 hazırlanıyor. Biraz sonra tekrar dene.")
    async with CONVERT_LOCK:
        try:
            directory, file_path, filename = await run_in_threadpool(convert_video, url)
        except FriendlyError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return FileResponse(
        file_path,
        filename=filename,
        media_type="audio/mpeg",
        background=BackgroundTask(shutil.rmtree, directory, ignore_errors=True),
    )


@app.exception_handler(413)
async def too_large_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=413, content={"detail": "Dosya çok büyük."})
