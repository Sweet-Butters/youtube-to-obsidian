"""Unit tests for vault_indexer — pure file I/O, no network."""
from __future__ import annotations

from pathlib import Path

from notes_project.vault_indexer import ExistingNote, format_for_prompt, index_vault


def _write_note(dir_: Path, name: str, fm: dict) -> None:
    import yaml

    body = "---\n" + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False) + "---\n# body\n"
    (dir_ / name).write_text(body, encoding="utf-8")


def test_index_vault_empty(tmp_path):
    assert index_vault(tmp_path) == []


def test_index_vault_skips_malformed(tmp_path):
    (tmp_path / "YouTube").mkdir()
    (tmp_path / "YouTube" / "no-frontmatter.md").write_text("# raw text\n")
    (tmp_path / "YouTube" / "bad-yaml.md").write_text("---\nthis: is: bad: yaml:\n---\nbody")
    (tmp_path / "YouTube" / "no-title.md").write_text("---\nchannel: X\n---\nbody")
    assert index_vault(tmp_path) == []


def test_index_vault_sorts_by_date_desc(tmp_path):
    (tmp_path / "YouTube").mkdir()
    _write_note(tmp_path / "YouTube", "older.md", {
        "title": "Old Note", "category": "Education",
        "date_watched": "2026-01-01", "tags": ["a"],
    })
    _write_note(tmp_path / "YouTube", "newer.md", {
        "title": "New Note", "category": "Science & Technology",
        "date_watched": "2026-05-15", "tags": ["b"],
    })
    notes = index_vault(tmp_path)
    assert len(notes) == 2
    assert notes[0].title == "New Note"
    assert notes[1].title == "Old Note"


def test_index_vault_respects_max(tmp_path):
    (tmp_path / "YouTube").mkdir()
    for i in range(10):
        _write_note(tmp_path / "YouTube", f"n{i}.md", {
            "title": f"Note {i}",
            "date_watched": f"2026-05-{i + 1:02d}",
        })
    assert len(index_vault(tmp_path, max_notes=3)) == 3


def test_format_for_prompt_empty():
    assert format_for_prompt([]) == ""


def test_format_for_prompt_renders_wikilinks():
    notes = [
        ExistingNote(title="Hello World", category="Education",
                     date_watched="2026-05-15", tags=[]),
        ExistingNote(title="한글 노트", category="과학/기술",
                     date_watched="2026-05-14", tags=[]),
    ]
    out = format_for_prompt(notes)
    assert "[[Hello World]]" in out
    assert "[[한글 노트]]" in out
    assert "category: Education" in out
    assert "category: 과학/기술" in out
