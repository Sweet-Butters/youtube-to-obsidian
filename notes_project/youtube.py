"""YouTube metadata + transcript fetching."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

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


def fetch_transcript(video_id: str, *, prefer_lang: str | None = None) -> tuple[str, str, str]:
    """Return (transcript_text, language_code, caption_type).

    caption_type is 'manual' or 'auto'. Raises LookupError if no captions exist
    (v1 deliberately does NOT support Whisper fallback).
    """
    from youtube_transcript_api import YouTubeTranscriptApi  # heavy, defer import

    api = YouTubeTranscriptApi()
    transcripts = api.list(video_id)

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
