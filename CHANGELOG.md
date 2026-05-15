# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/Sweet-Butters/youtube-to-obsidian/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/Sweet-Butters/youtube-to-obsidian/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Sweet-Butters/youtube-to-obsidian/releases/tag/v0.1.0
