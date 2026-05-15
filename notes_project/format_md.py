"""Format frontmatter + markdown body for an Obsidian note."""
from __future__ import annotations

import re
from datetime import date

import yaml

from auto_project.youtube.categories import lookup

from .summarize import Summary
from .youtube import VideoMeta


def filename(meta: VideoMeta, watched: date) -> str:
    slug = _slug(meta.title)[:80]
    return f"{watched.isoformat()}_{slug}_[{meta.video_id}].md"


def render(
    meta: VideoMeta,
    transcript_lang: str,
    caption_type: str,
    summary: Summary,
    transcript: str,
    *,
    watched: date,
    display_lang: str = "ko",
) -> str:
    cat_en, cat_ko = lookup(meta.category_id)
    display_category = cat_ko if display_lang == "ko" else cat_en

    fm = {
        "title": meta.title,
        "channel": meta.channel,
        "channel_url": meta.channel_url,
        "url": f"https://www.youtube.com/watch?v={meta.video_id}",
        "video_id": meta.video_id,
        "upload_date": meta.upload_date,
        "date_watched": watched.isoformat(),
        "duration": meta.duration,
        "language": transcript_lang,
        "caption_type": caption_type,
        "category_id": meta.category_id,
        "category_en": cat_en,
        "category_ko": cat_ko,
        "category": display_category,
        "tags": ["youtube", *summary.tags],
    }
    fm_yaml = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).strip()

    parts = [
        f"---\n{fm_yaml}\n---\n",
        f"# {meta.title}",
        "",
        "## Summary",
        "",
        summary.short,
        "",
        "## Key Points",
        "",
        summary.long,
        "",
    ]
    if summary.key_terms:
        parts += ["## Key Terms", "", ", ".join(summary.key_terms), ""]
    if summary.quotes:
        parts += ["## Quotes", ""]
        for q in summary.quotes:
            ts = q.get("ts", "")
            text = q.get("text", "")
            parts.append(f"> {text}  \n> — `{ts}`")
            parts.append("")
    parts += ["## Transcript", "", transcript, ""]
    return "\n".join(parts)


def _slug(text: str) -> str:
    s = re.sub(r"[^\w가-힣]+", "-", text.strip().lower())
    return s.strip("-") or "untitled"
