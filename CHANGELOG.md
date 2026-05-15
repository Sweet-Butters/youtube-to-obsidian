# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-05-15

### Added

- **3-tier transcript fallback** in `notes_project/youtube.py`:
  1. Direct fetch (no proxy) — fast path, works from residential IPs.
  2. **WebShare residential proxy** — controlled by `WEBSHARE_USER` / `WEBSHARE_PASS` env vars. Bypasses YouTube's cloud-IP block, making the pipeline runnable on hosted GitHub Actions runners.
  3. **Local Whisper transcription** — controlled by `ENABLE_WHISPER=1` and `WHISPER_MODEL=<size>` env vars. Downloads audio via `yt-dlp` and transcribes with `faster-whisper`. Handles caption-less videos. Slow (CPU) but free.
- **Hosted-runner fallback workflow** (`summarize-video-fallback.yml`): runs on `ubuntu-latest` with WebShare proxy enabled. Whisper is intentionally **not** enabled here (CPU-only hosted runners would burn CI minutes). Designed to be dispatched by the bot when the self-hosted runner is offline.
- **Automatic Zettelkasten backlinks** (`notes_project/vault_indexer.py`): the pipeline now scans the vault for the 50 most-recent existing notes, surfaces them as context to the LLM, and the LLM embeds `[[exact title]]` references in `summary_long` when topically relevant. Obsidian renders these as live backlinks, building a knowledge graph organically as the vault grows.
- `tests/test_vault_indexer.py` — 6 unit tests covering empty vaults, malformed frontmatter, date-descending sort, max-notes capping, and the prompt-formatting helper.

### Changed

- `notes_project/summarize.py::summarize()` accepts an optional `existing_notes: Iterable[ExistingNote]` keyword argument. When provided, the LLM system prompt is augmented with a wikilink-context block and instructed to embed `[[title]]` references for topically related vault notes.
- `notes_project/__main__.py` now has 5 stages instead of 4 (the new `[4/5] vault: indexed N existing notes for backlinks` step runs between transcript fetch and summarization).
- `summarize-video.yml` (self-hosted workflow) now sets `ENABLE_WHISPER=1` and `WHISPER_MODEL=base` so caption-less videos auto-transcribe locally. The hosted-fallback workflow leaves Whisper disabled.
- `requirements.txt` and `pyproject.toml`: added `faster-whisper>=1.0.0` as a base dependency. It's only imported when `ENABLE_WHISPER=1`, so it's safe to install on every runner — install cost (~150MB model on first use) is paid only on the self-hosted side.
- `notes_project/__init__.py`: version bumped to `0.2.0`.

### Why this matters

v0.1.x required the self-hosted runner to be online. If your laptop slept or
WSL was shut down, every YouTube share queued up and went nowhere. v0.2.0
makes the pipeline survive runner downtime:

- The companion `auto_project` bot (v0.6.0) detects an offline self-hosted runner and dispatches the fallback workflow on GHA-hosted runners instead.
- The fallback path uses WebShare's free residential proxy tier (10 IPs, 1 GB/month) — enough for tens of thousands of transcript fetches.
- When the self-hosted runner is online, the fast path runs (no proxy, plus Whisper for caption-less videos). When it's offline, the slower-but-always-available fallback runs.

Net effect: the pipeline goes from "works while my laptop is on" to "always works", with no per-month cost.

The backlink feature is an unrelated but complementary v2 win: as your vault grows, each new note progressively cross-references the existing ones, turning a flat list of summaries into a navigable knowledge graph — without manual linking.

## [0.1.1] - 2026-05-15

### Added

- **"Common pitfalls (mobile)" section** in `README.md` (English) and `README.ko.md` (Korean), with detailed walkthroughs of the three setup snags encountered during real-world testing:
  1. `Git: Pull` command appears to be a no-op until `Author name` and `Author email` are filled in (required even when `Disable push` is enabled — counterintuitive).
  2. Sync trigger discoverability on mobile — four methods documented (command palette, left ribbon, mobile toolbar, app restart).
  3. Subdirectory vault breaks `isomorphic-git` walk-up on Android — vault must be opened at the repo root and non-vault paths excluded via `Settings → Files & links → Excluded files`.
- Cross-reference banner at the top of the "Mobile Obsidian setup" section pointing readers to the pitfalls section before they start.
- `CHANGELOG.md` (this file) following the [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) convention.
- Mention of `CHANGELOG.md` in the suggested `Excluded files` list (so it doesn't clutter the mobile file tree).

### Changed

- `CLAUDE.md` "Mobile (Android) gotchas" section rewritten as "Mobile (Android) gotchas — discovered during real setup", with each pitfall (A/B/C) elaborated for AI-assisted debugging context.
- Table of contents in both READMEs updated to include the new "Common pitfalls" entry.

### Why this matters

The original `0.1.0` README listed the author-identity requirement as a single line in a troubleshooting table. In practice, that line was easy to miss — the symptom is *complete silence* (no error, no log, no toast), so users naturally look elsewhere first. Promoting it to a top-level section with the symptom → cause → fix pattern should save the next person an hour.

## [0.1.0] - 2026-05-15

### Added

- Initial public release of the `youtube-to-obsidian` pipeline.
- End-to-end flow: YouTube URL → YouTube Data API metadata → `youtube-transcript-api` captions → `auto_project.llm` (Gemini / Groq / Cerebras free-tier router) summarization → structured Obsidian Markdown note.
- Bilingual category support: every note's frontmatter stores `category_en`, `category_ko`, and a user-editable `category` field that mirrors one based on `--lang`.
- YAML frontmatter contract: `video_id`, `upload_date`, `date_watched`, `duration`, `language`, `caption_type`, `category_id`, `tags`, etc.
- Filename convention `YYYY-MM-DD_title-slug_[video_id].md` (Korean characters preserved).
- GitHub Actions workflow (`workflow_dispatch`) on self-hosted runners (mandatory: GitHub-hosted runners are blocked by YouTube anti-scraping).
- Optional `LOCAL_VAULT_PATH` repository variable for instant local Obsidian sync after each push.
- `scripts/recategorize.py` for bulk category-display-language flips and per-note overrides.
- `vault.example/` template with Dataview-powered `Dashboard.md`, frontmatter template, and `.obsidian/` plugin configuration.
- Bilingual documentation: English `README.md` and Korean `README.ko.md`.
- `CLAUDE.md` for AI-assisted contributors.
- Robust JSON parser in `summarize.py` (handles markdown code fences, trailing prose, multiple candidate objects, escape-aware brace balancing) with one automatic LLM retry on parse failure.
- MIT license.

### Notes

- Designed for **zero-cost personal use** via free-tier APIs and self-hosted GitHub Actions runners.
- Pairs with [`auto_project`](https://github.com/Sweet-Butters/auto_project)'s Telegram bot (`URL_ROUTES` env var) for phone-triggered runs.
- Inspiration acknowledged in `README.md` — see *Acknowledgments*.

[Unreleased]: https://github.com/Sweet-Butters/youtube-to-obsidian/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Sweet-Butters/youtube-to-obsidian/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/Sweet-Butters/youtube-to-obsidian/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Sweet-Butters/youtube-to-obsidian/releases/tag/v0.1.0
