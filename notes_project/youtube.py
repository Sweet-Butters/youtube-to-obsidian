"""YouTube metadata + transcript fetching with 3-tier fallback.

Transcript fetch order:
  1. Direct (no proxy)        — fast, works from residential IPs.
  2. WebShare residential     — bypasses cloud-IP blocks (GHA-hosted runners).
                                Active if WEBSHARE_USER/WEBSHARE_PASS env vars set.
  3. Whisper local            — handles caption-less videos. CPU-heavy, free.
                                Active if ENABLE_WHISPER=1 (and faster-whisper installed).

Whisper is gated by an env var because it adds a ~150MB model download on
first use and is much slower than caption fetch — typically only enabled
on self-hosted runners with permanent compute.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import requests

_VIDEO_ID_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|embed/|shorts/|v/)|youtu\.be/)([A-Za-z0-9_-]{11})"
)


def extract_video_id(url: str) -> str:
    m = _VIDEO_ID_RE.search(url)
    if not m:
        raise ValueError(f"Could not extract video id from URL: {url!r}")
    return m.group(1)


@dataclass
class VideoMeta:
    video_id: str
    title: str
    channel: str
    channel_url: str
    upload_date: str           # YYYY-MM-DD
    duration: str              # human-readable "1h 23m 14s"
    description: str
    category_id: int | None    # YouTube official categoryId


def fetch_metadata(video_id: str, *, api_key: str | None = None) -> VideoMeta:
    """Fetch metadata via YouTube Data API v3.

    Provides the authoritative `categoryId` we use for classification.
    The Data API is authenticated and works from any IP — only the unofficial
    caption-scraping path needs the proxy fallback.
    """
    api_key = api_key or os.environ["YOUTUBE_API_KEY"]
    resp = requests.get(
        "https://www.googleapis.com/youtube/v3/videos",
        params={
            "id": video_id,
            "part": "snippet,contentDetails",
            "key": api_key,
        },
        timeout=15,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    if not items:
        raise LookupError(f"Video not found or private: {video_id}")

    item = items[0]
    snip = item["snippet"]
    return VideoMeta(
        video_id=video_id,
        title=snip["title"],
        channel=snip["channelTitle"],
        channel_url=f"https://www.youtube.com/channel/{snip['channelId']}",
        upload_date=snip["publishedAt"][:10],
        duration=_iso8601_duration_to_human(item["contentDetails"]["duration"]),
        description=snip.get("description", ""),
        category_id=int(snip["categoryId"]) if snip.get("categoryId") else None,
    )


def _iso8601_duration_to_human(iso: str) -> str:
    """PT1H23M14S -> '1h 23m 14s'."""
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
    if not m:
        return iso
    h, mn, s = (int(x) if x else 0 for x in m.groups())
    parts = []
    if h:
        parts.append(f"{h}h")
    if mn or h:
        parts.append(f"{mn}m")
    parts.append(f"{s}s")
    return " ".join(parts)


# ----------------------------------------------------------------------------
# Transcript fetching — 3-tier fallback
# ----------------------------------------------------------------------------

def fetch_transcript(
    video_id: str,
    *,
    prefer_lang: str | None = None,
) -> tuple[str, str, str]:
    """Return (transcript_text, language_code, caption_type).

    caption_type ∈ {'manual', 'auto', 'whisper'}.

    Tries direct → WebShare proxy → Whisper, controlled by env vars.
    Raises LookupError if all configured paths fail.
    """
    direct_err: Exception | None = None

    # Tier 1: direct (no proxy)
    try:
        return _fetch_via_api(video_id, prefer_lang=prefer_lang, proxy_config=None)
    except _IPBlocked as e:
        direct_err = e  # fall through to proxy
    except LookupError:
        # No captions at all → API won't change that. Try Whisper if enabled.
        if _whisper_enabled():
            return _fetch_via_whisper(video_id)
        raise

    # Tier 2: WebShare proxy
    proxy_config = _build_webshare_proxy_config()
    if proxy_config is not None:
        try:
            return _fetch_via_api(video_id, prefer_lang=prefer_lang, proxy_config=proxy_config)
        except _IPBlocked:
            pass  # rare — WebShare residential IPs are normally allowed
        except LookupError:
            if _whisper_enabled():
                return _fetch_via_whisper(video_id)
            raise

    # Tier 3: Whisper local transcription
    if _whisper_enabled():
        return _fetch_via_whisper(video_id)

    raise direct_err


def _fetch_via_api(
    video_id: str,
    *,
    prefer_lang: str | None,
    proxy_config,
) -> tuple[str, str, str]:
    """Fetch captions via youtube-transcript-api. Raises _IPBlocked on cloud-IP block."""
    from youtube_transcript_api import YouTubeTranscriptApi

    api = YouTubeTranscriptApi(proxy_config=proxy_config) if proxy_config else YouTubeTranscriptApi()
    try:
        transcripts = api.list(video_id)
    except Exception as e:
        if type(e).__name__ in ("RequestBlocked", "IpBlocked"):
            raise _IPBlocked(str(e)) from e
        raise

    chosen = None
    if prefer_lang:
        try:
            chosen = transcripts.find_transcript([prefer_lang])
        except Exception:
            chosen = None
    if chosen is None:
        manual_langs = [t.language_code for t in transcripts if not t.is_generated]
        if manual_langs:
            try:
                chosen = transcripts.find_manually_created_transcript(manual_langs)
            except Exception:
                chosen = None
    if chosen is None:
        auto_langs = [t.language_code for t in transcripts if t.is_generated]
        if auto_langs:
            try:
                chosen = transcripts.find_generated_transcript(auto_langs)
            except Exception:
                chosen = None
    if chosen is None:
        raise LookupError(f"No usable captions for video {video_id}")

    fetched = chosen.fetch()
    text = "\n".join(snippet.text for snippet in fetched)
    caption_type = "auto" if chosen.is_generated else "manual"
    return text, chosen.language_code, caption_type


def _build_webshare_proxy_config():
    """Returns a WebshareProxyConfig if creds are set, else None."""
    user = os.environ.get("WEBSHARE_USER")
    password = os.environ.get("WEBSHARE_PASS")
    if not (user and password):
        return None
    from youtube_transcript_api.proxies import WebshareProxyConfig
    return WebshareProxyConfig(
        proxy_username=user,
        proxy_password=password,
    )


def _whisper_enabled() -> bool:
    return os.environ.get("ENABLE_WHISPER", "").strip() in ("1", "true", "TRUE", "yes")


def _fetch_via_whisper(video_id: str) -> tuple[str, str, str]:
    """Download audio with yt-dlp and transcribe with faster-whisper.

    Returns (text, language, 'whisper'). Slow (CPU) but free and offline.
    Model name configurable via WHISPER_MODEL env var (default: 'base').
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise RuntimeError(
            "ENABLE_WHISPER=1 but faster-whisper is not installed. "
            "Install with: pip install faster-whisper"
        ) from e

    with tempfile.TemporaryDirectory() as tmp:
        audio_path = Path(tmp) / "audio.m4a"
        subprocess.run(
            [
                "yt-dlp",
                "-f", "bestaudio[ext=m4a]/bestaudio",
                "-o", str(audio_path),
                "--quiet",
                "--no-warnings",
                f"https://www.youtube.com/watch?v={video_id}",
            ],
            check=True,
            timeout=300,
        )

        model_name = os.environ.get("WHISPER_MODEL", "base")
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        segments, info = model.transcribe(str(audio_path), beam_size=1)
        text = "\n".join(seg.text.strip() for seg in segments if seg.text.strip())

    return text, info.language, "whisper"


class _IPBlocked(Exception):
    """Raised when YouTube blocks the request by IP (cloud-provider block)."""
