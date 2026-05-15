"""Scan the vault for existing notes and surface them as backlink context.

The LLM uses this list to embed `[[note title]]` references in new summaries
when topically related. Obsidian renders these as live backlinks.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class ExistingNote:
    title: str
    category: str
    date_watched: str
    tags: list[str]


def index_vault(vault_dir: Path | str, *, max_notes: int = 50) -> list[ExistingNote]:
    """Return the most-recently-watched notes (up to max_notes) for backlink context.

    Reads YAML frontmatter from each .md under <vault>/YouTube/. Notes without
    parseable frontmatter or a `title` are skipped silently.
    """
    base = Path(vault_dir) / "YouTube"
    if not base.is_dir():
        return []

    notes: list[ExistingNote] = []
    for md_file in base.glob("*.md"):
        try:
            text = md_file.read_text(encoding="utf-8")
        except OSError:
            continue
        if not text.startswith("---\n"):
            continue
        end = text.find("\n---\n", 4)
        if end < 0:
            continue
        try:
            fm = yaml.safe_load(text[4:end]) or {}
        except yaml.YAMLError:
            continue
        title = fm.get("title")
        if not title:
            continue
        notes.append(
            ExistingNote(
                title=str(title),
                category=str(fm.get("category", "")),
                date_watched=str(fm.get("date_watched", "")),
                tags=list(fm.get("tags", []) or []),
            )
        )

    notes.sort(key=lambda n: n.date_watched, reverse=True)
    return notes[:max_notes]


def format_for_prompt(notes: list[ExistingNote]) -> str:
    """One-line-per-note summary suitable for inclusion in an LLM prompt."""
    if not notes:
        return ""
    lines = [
        "Existing notes in this vault (you MAY embed `[[exact title]]` in summary_long "
        "when topically relevant — Obsidian renders these as live backlinks):",
    ]
    for n in notes:
        lines.append(f"- [[{n.title}]]  (category: {n.category})")
    return "\n".join(lines) + "\n"
