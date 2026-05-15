"""CLI entry: python -m notes_project <url> [--lang ko|en] [--vault ./vault]"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from . import format_md, summarize, vault_indexer, youtube


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

    vault_dir = Path(args.vault)

    vid = youtube.extract_video_id(args.url)
    print(f"[1/5] video_id = {vid}", file=sys.stderr)

    meta = youtube.fetch_metadata(vid)
    print(f"[2/5] metadata: {meta.title!r} ({meta.duration})", file=sys.stderr)

    transcript, lang, caption_type = youtube.fetch_transcript(vid)
    print(
        f"[3/5] transcript: {len(transcript)} chars, lang={lang}, type={caption_type}",
        file=sys.stderr,
    )

    existing = vault_indexer.index_vault(vault_dir)
    print(f"[4/5] vault: indexed {len(existing)} existing notes for backlinks",
          file=sys.stderr)

    summ = summarize.summarize(
        transcript, title=meta.title, channel=meta.channel, lang=lang,
        existing_notes=existing,
    )
    print(
        f"[5/5] summary: {len(summ.tags)} tags, {len(summ.key_terms)} terms",
        file=sys.stderr,
    )

    watched = date.today()
    body = format_md.render(
        meta, lang, caption_type, summ, transcript,
        watched=watched, display_lang=args.lang,
    )
    out_dir = vault_dir / "YouTube"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / format_md.filename(meta, watched)
    out_path.write_text(body, encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
