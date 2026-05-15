# youtube-to-obsidian — Claude context

Public template repo. YouTube video → AI summary → Obsidian vault. Designed for zero-cost personal use; runs as a **hybrid** GitHub Actions pipeline that prefers a self-hosted runner (residential IP, Whisper-capable) and falls back to a hosted-runner workflow with a WebShare residential proxy when the self-hosted machine is offline.

> This file gives Claude (or any AI assistant) the context it needs to help with this project. It's deliberately concise — full user-facing docs live in [README.md](README.md) / [README.ko.md](README.ko.md).

## Architecture (one-liner)

```
[Phone Telegram] → [Cloud Run auto_project bot ≥ v0.6.0]
                          │
                          │  checks: GET /repos/{repo}/actions/runners
                          │  → online runner exists?
                          │
       ┌──────────────────┴───────────────────┐
       │ yes (fast)                           │ no (fallback)
       ▼                                      ▼
[summarize-video.yml]                  [summarize-video-fallback.yml]
   runs-on: self-hosted                    runs-on: ubuntu-latest
   residential IP, ENABLE_WHISPER=1        WebShare proxy, Whisper off
       │                                      │
       └──────────────────┬───────────────────┘
                          ▼
       1. fetch_metadata    (YouTube Data API v3, any IP)
       2. fetch_transcript  (3-tier: direct → WebShare → Whisper)
       3. vault_indexer     (scan vault/YouTube for backlink ctx)
       4. summarize         (auto_project.llm, embeds [[wikilinks]])
       5. render_md         (frontmatter + body)
       6. commit + push     (vault/YouTube/YYYY-MM-DD_slug_[id].md)
       7. (fast path only) sync local clone via LOCAL_VAULT_PATH
                          ▼
       [Local Obsidian file watcher + Phone Obsidian Git pull]
```

## Dependencies

- `auto_project @ v0.5.0` (public framework) — `llm`, `notify`, `state`, `youtube.categories`
- `youtube-transcript-api` (>=1.2) — instance-based API (`api.list()`, `api.fetch()`), supports `WebshareProxyConfig`
- `yt-dlp` — audio download for Whisper fallback
- `faster-whisper` (>=1.0) — local Whisper transcription, gated by `ENABLE_WHISPER=1`. Lazy-imported; safe to install on all runners.
- `PyYAML` — frontmatter (de)serialization

## File naming

`vault/YouTube/YYYY-MM-DD_title-slug_[video_id].md`

- Convention borrowed from [JimmySadek/youtube-fetcher-to-markdown](https://github.com/JimmySadek/youtube-fetcher-to-markdown).
- Slug keeps Korean characters (`[^\w가-힣]+` → `-`).
- 80-char trim. Video id in brackets prevents collisions.

## Frontmatter contract

Each note's frontmatter MUST include:

```yaml
title: str
channel: str
channel_url: str
url: str (youtube)
video_id: str (11 chars)
upload_date: YYYY-MM-DD
date_watched: YYYY-MM-DD
duration: "Xh Ym Zs"
language: ISO 639-1
caption_type: manual | auto
category_id: int (YouTube official)
category_en: str
category_ko: str
category: str (mirrors _en or _ko per display_lang)
tags: list[str] (kebab-case, ASCII, starts with "youtube")
```

The `category` field is the **user-editable display value**. `category_id` / `category_en` / `category_ko` are the source of truth and should not be edited by hand.

## What changed from v0.1.x to v0.2.0

**v0.1.x limitations** and how v0.2.0 resolves them:

| v0.1.x limitation | v0.2.0 resolution |
|---|---|
| Pipeline only works while the self-hosted runner is online (laptop must be on) | Bot picks **fallback workflow** when no runner is online — uses GHA-hosted runner + WebShare proxy. Pipeline now always runs. |
| Videos without captions error out (no Whisper) | **`ENABLE_WHISPER=1`** on the fast workflow activates local `faster-whisper` transcription. Slow (CPU) but free. Disabled on fallback workflow to save CI minutes. |
| Notes are standalone — no cross-references | **vault_indexer** scans up to 50 most-recent vault notes, surfaces (title, category) to the LLM, which embeds `[[wikilinks]]` in `summary_long` when topically relevant. Knowledge graph forms organically. |

## Intentional limitations (still present)

- **Single language summary.** Output language matches transcript language. No translation step.
- **Tags are English kebab-case only.** Keeps cross-vault deduplication clean.
- **WebShare free tier may 429.** Free residential proxies are shared and YouTube rate-limits popular ones. Architecture works, but a given fallback request may fail and need a retry. Upgrade to WebShare paid (~$2.99/mo) for stickier sessions if this becomes a real problem.

## Setup checklist (for a fresh fork)

1. ◌ `gh repo fork --clone` (or template-use)
2. ◌ `mv vault.example vault` and commit
3. ◌ GitHub Secrets: `YOUTUBE_API_KEY`, `GEMINI_API_KEY` (use `gcloud → gh secret set` pipeline from README)
4. ◌ (Recommended) GitHub Secrets: `WEBSHARE_USER`, `WEBSHARE_PASS` — required for the fallback path. Skip if you only want the fast path.
5. ◌ Self-hosted runner installed + registered + systemd user service (for the fast path)
6. ◌ (Optional) `LOCAL_VAULT_PATH` repo variable set if you want instant local sync
7. ◌ (Optional) Connect `auto_project` Telegram bot (≥ v0.6.0) for phone-triggered runs with automatic hybrid routing
8. ◌ Open `vault/` in Obsidian, install Dataview plugin
9. ◌ (Mobile) Termux + clone, Obsidian Git plugin with required settings (Author name/email MUST be set even with Disable push)

## Self-hosted runner notes

- Service name: `yt-obsidian-runner` (user-level systemd, no sudo for service itself)
- Location: `~/actions-runner/`
- Status: `systemctl --user status yt-obsidian-runner`
- Reboot survival needs `sudo loginctl enable-linger <user>` (one-time sudo prompt)
- Without linger, the runner stops when the user logs out

## Mobile (Android) gotchas — discovered during real setup

These three pitfalls cost meaningful time during our initial setup. They are documented in README's "Common pitfalls (mobile)" section for end users; Claude should be aware of them when helping debug mobile sync:

### A. "Git: Pull" runs no-op until author identity is set

Obsidian Git's `pull` (and all other git commands) silently does nothing if `Author name for commits` AND `Author email for commits` are empty. This applies **even when `Disable push` is ON**, which is counterintuitive — a user who plans only to pull will reasonably assume no author config is needed. The plugin pre-validates author identity before running any operation.

**When debugging "sync command does nothing"**: first check the two author fields. They can be set to any string (e.g. `phone-readonly` / `<YOUR_EMAIL>`) — the values don't have to be real.

### B. Sync trigger discoverability on mobile

Mobile Obsidian has no default sync icon. Trigger sources, in order of how a user discovers them:

1. Command palette (top-bar search icon → "pull")
2. Left sidebar ribbon (swipe from left edge)
3. Mobile toolbar (must be configured: Settings → Appearance → Manage toolbar)
4. App restart with `Pull on startup` enabled

When helping a user who "can't find the sync button", check which of these they've tried. The command palette is the most reliable fallback.

### C. Subdirectory vault breaks isomorphic-git on Android

If the vault is opened at `repo/vault/` and `.git` lives at `repo/.git`, mobile Obsidian Git typically can't find the parent. The fix is to open `repo/` as the vault (not the subfolder) and add non-vault paths to **Settings → Files & links → Excluded files** to hide them from the file tree.

This is **not** an issue on desktop Obsidian Git, where filesystem walk-up works fine. Only mobile (Android, scoped storage) is affected.

## Related repos

- [`auto_project`](https://github.com/Sweet-Butters/auto_project) (public, v0.5.0) — framework + Telegram bot
- Design influences: [Jimmy's youtube-fetcher](https://github.com/JimmySadek/youtube-fetcher-to-markdown), [Defuddle](https://github.com/spaceage64/claude-defuddle), [shorts-saver-bot](https://github.com/Stnslv-k/shorts-saver-bot), [obsidian-vault-agent](https://github.com/tuan3w/obsidian-vault-agent)

## When working in this codebase

- The `notes_project/` package is the entry point: `python -m notes_project <url>`.
- `summarize.py` calls `auto_project.llm.call()` — robust JSON parser with one automatic retry on parse failure.
- `format_md.py` imports category mapping from `auto_project.youtube.categories` (NOT a local module).
- Workflow is on a self-hosted runner (`runs-on: [self-hosted, linux]`); the `LOCAL_VAULT_PATH` step is opt-in.
- Tests run without network: `pytest tests/`.

## Versioning

- This template repo: tag v0.X.Y on each release.
- The `auto_project` framework is pinned by tag in `pyproject.toml` and `requirements.txt`. Both MUST stay in sync — the workflow uses `pip install -e .` which reads `pyproject.toml` only.
- Breaking pipeline output format → major bump.
- New features / config knobs → minor bump.
- Bug fixes / docs → patch.
