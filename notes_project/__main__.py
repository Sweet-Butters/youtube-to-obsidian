"""CLI entry: python -m notes_project <url> [--lang ko|en]"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from . import format_md, summarize, youtube


def main() -> int:
    ap = argparse.ArgumentParser(description="YouTube -> Obsidian markdown note")
    ap.add_argument("url", help="YouTube video URL")
    ap.add_argument(
        "--lang", default="ko", choices=["ko", "en"],
        help="Display language for the `category` frontmatter field (default: ko)"
    )
    ap.add_argument(
        "--vault", default="vault",
        help="Vault root (default: ./vault). Output lands in <vault>/YouTube/"
    )
    args = ap.parse_args()

    vid = youtube.extract_video_id(args.url)
    print(f"[1/4] video_id = {vid}", file=sys.stderr)

    meta = youtube.fetch_metadata(vid)
    print(f"[2/4] metadata: {meta.title!r} ({meta.duration})", file=sys.stderr)

    transcript, lang, caption_type = youtube.fetch_transcript(vid)
    print(
        f"[3/4] transcript: {len(transcript)} chars, lang={lang}, type={caption_type}",
        file=sys.stderr,
    )

    summ = summarize.summarize(
        transcript, title=meta.title, channel=meta.channel, lang=lang
    )
    print(
        f"[4/4] summary: {len(summ.tags)} tags, {len(summ.key_terms)} terms",
        file=sys.stderr,
    )

    watched = date.today()
    body = format_md.render(
        meta, lang, caption_type, summ, transcript,
        watched=watched, display_lang=args.lang,
    )
    out_dir = Path(args.vault) / "YouTube"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / format_md.filename(meta, watched)
    out_path.write_text(body, encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
