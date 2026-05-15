"""Bulk re-categorize notes already in the vault.

Examples:
    # Flip display language for every note (ko -> en):
    python scripts/recategorize.py vault/YouTube --display-lang en

    # Override one note's category manually:
    python scripts/recategorize.py vault/YouTube/2026-01-01_xxx_[abc123].md --new-category "Education"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("target", help="vault dir or a single .md file")
    ap.add_argument(
        "--display-lang", choices=["ko", "en"],
        help="Set `category` to mirror category_ko (ko) or category_en (en) on every note"
    )
    ap.add_argument(
        "--new-category",
        help="Force a specific category value (only valid for a single .md target)"
    )
    args = ap.parse_args()

    target = Path(args.target)
    if args.new_category and not target.is_file():
        ap.error("--new-category requires a single .md file as target")

    files = [target] if target.is_file() else sorted(target.rglob("*.md"))
    changed = 0
    for f in files:
        text = f.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            continue
        end = text.find("\n---\n", 4)
        if end < 0:
            continue
        fm = yaml.safe_load(text[4:end]) or {}
        original = dict(fm)
        if args.new_category:
            fm["category"] = args.new_category
        elif args.display_lang == "ko" and "category_ko" in fm:
            fm["category"] = fm["category_ko"]
        elif args.display_lang == "en" and "category_en" in fm:
            fm["category"] = fm["category_en"]
        if fm != original:
            new_fm = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).strip()
            f.write_text(f"---\n{new_fm}\n---\n{text[end + 5:]}", encoding="utf-8")
            changed += 1
            print(f"  updated: {f}", file=sys.stderr)
    print(f"Changed {changed} / {len(files)} files", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
