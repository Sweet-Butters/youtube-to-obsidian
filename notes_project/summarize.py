"""LLM-based summarization producing structured output.

Uses auto_project.llm which routes Gemini -> Groq -> Cerebras (free tiers).

Since v2, accepts an optional list of existing vault notes — the LLM
embeds `[[exact title]]` references where topically relevant, building
a Zettelkasten-style backlink graph automatically.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Iterable

from auto_project import llm

from .vault_indexer import ExistingNote, format_for_prompt

_SYSTEM = """You are a professional research assistant. Given a YouTube video transcript and metadata, produce a structured summary suitable for a permanent knowledge base.

Output ONLY a single JSON object. No code fences (```), no prose before or after, no comments. Every string MUST escape interior double quotes as \\" and escape backslashes as \\\\. Do not use raw newlines inside string values — use \\n.

The JSON object has these fields:
- "summary_short": string. 2-3 sentence overview, plain text.
- "summary_long": list of 6-12 strings, each a bullet point covering a key argument/claim/evidence/conclusion. No leading "- ", just the content. When an existing vault note is topically related, embed its exact title as a Markdown wikilink `[[Note Title]]` inside the bullet — but ONLY when there is a genuine conceptual link, never for filler.
- "key_terms": list of 3-8 strings, important terms/concepts (just the term, no definitions).
- "tags": list of 3-7 lowercase kebab-case strings (e.g. "transformer-architecture"). ASCII only, no spaces, no Korean characters.
- "quotes": list of up to 5 objects, each {"text": "...", "ts": "MM:SS or HH:MM:SS"}. Use [] if no standout quotes.

Write the content of summary_short / summary_long / key_terms / quotes in the same language as the transcript. The tags field is always English kebab-case.
"""


@dataclass
class Summary:
    short: str
    long: str
    key_terms: list[str]
    tags: list[str]
    quotes: list[dict]


def summarize(
    transcript: str,
    *,
    title: str,
    channel: str,
    lang: str,
    existing_notes: Iterable[ExistingNote] | None = None,
) -> Summary:
    """Call the LLM and parse a structured summary. Retries once on parse error.

    If `existing_notes` is provided, the LLM is asked to embed `[[wikilinks]]`
    in summary_long where topically relevant — building a Zettelkasten-style
    backlink graph as new notes accumulate.
    """
    backlink_context = ""
    if existing_notes:
        notes_list = list(existing_notes)
        if notes_list:
            backlink_context = "\n\n" + format_for_prompt(notes_list)

    prompt = (
        f"Title: {title}\n"
        f"Channel: {channel}\n"
        f"Transcript language: {lang}\n"
        f"{backlink_context}"
        f"\nTranscript:\n{transcript[:50_000]}\n"
    )
    raw = llm.call(prompt, system=_SYSTEM, timeout=120)
    try:
        data = _parse_json(raw)
    except ValueError:
        retry_prompt = (
            prompt
            + "\n\nIMPORTANT: Your previous output was not parseable JSON. "
            "Reply with ONLY a JSON object. No markdown, no code fences, no commentary. "
            "Escape every interior double quote as \\\". "
            "Do not use raw newlines inside string values — use \\n."
        )
        raw = llm.call(retry_prompt, system=_SYSTEM, timeout=120)
        data = _parse_json(raw)
    return Summary(
        short=_as_str(data.get("summary_short", "")),
        long=_as_bullets(data.get("summary_long", "")),
        key_terms=_as_list(data.get("key_terms", [])),
        tags=[_slugify_tag(t) for t in _as_list(data.get("tags", [])) if t],
        quotes=_as_list(data.get("quotes", [])),
    )


def _as_str(v) -> str:
    if isinstance(v, list):
        return "\n".join(str(x) for x in v).strip()
    return str(v).strip()


def _as_list(v) -> list:
    if isinstance(v, list):
        return v
    if isinstance(v, str) and v:
        return [s.strip() for s in v.split(",") if s.strip()]
    return []


def _as_bullets(v) -> str:
    """Normalize a bullet list (LLM returns either a string or a list of strings)."""
    if isinstance(v, list):
        out = []
        for item in v:
            s = str(item).strip()
            if not s:
                continue
            out.append(s if s.startswith(("-", "*")) else f"- {s}")
        return "\n".join(out)
    return str(v).strip()


def _parse_json(text: str) -> dict:
    """Robust JSON object extraction.

    Strips markdown code fences, then walks the string to find the first
    balanced { ... } block with string-aware escape handling. Falls back to
    scanning for later objects if the first candidate fails to parse.
    """
    s = text.strip()
    s = re.sub(r"^```(?:json|JSON)?\s*\n?", "", s)
    s = re.sub(r"\n?```\s*$", "", s)

    try:
        result = json.loads(s)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    start = s.find("{")
    last_err: Exception | None = None
    while start >= 0:
        depth = 0
        in_string = False
        escape = False
        end = -1
        for i in range(start, len(s)):
            c = s[i]
            if escape:
                escape = False
                continue
            if c == "\\":
                escape = True
                continue
            if c == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end < 0:
            break
        candidate = s[start:end + 1]
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError as e:
            last_err = e
        start = s.find("{", end + 1)
    raise ValueError(
        f"Could not parse JSON object (last error: {last_err}). "
        f"First 500 chars: {text[:500]!r}"
    )


def _slugify_tag(tag: str) -> str:
    s = re.sub(r"[^\w가-힣\-]+", "-", tag.strip().lower())
    return s.strip("-")
