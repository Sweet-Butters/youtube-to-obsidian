# youtube-to-obsidian — Claude context

Public template repo. YouTube video → AI summary → Obsidian vault. Designed for zero-cost personal use via GitHub Actions on a self-hosted runner.

> This file gives Claude (or any AI assistant) the context it needs to help with this project. It's deliberately concise — full user-facing docs live in [README.md](README.md) / [README.ko.md](README.ko.md).

## Architecture (one-liner)

```
[Phone Telegram] → [Cloud Run auto_project bot] → [GHA self-hosted runner]
                                                       │
                                                       ├─ YouTube Data API (categoryId)
                                                       ├─ youtube-transcript-api
                                                       └─ auto_project.llm (Gemini → Groq → Cerebras)
                                                       │
                                                       ▼
                                                  [vault/YouTube/*.md commit + push]
                                                       │
                                                       ▼
                                                  [Local Obsidian + phone Obsidian Git]
```

## Dependencies

- `auto_project @ v0.5.0` (public framework) — `llm`, `notify`, `state`, `youtube.categories`
- `youtube-transcript-api` (>=1.2) — instance-based API (`api.list()`, `api.fetch()`)
- `yt-dlp` — metadata enrichment fallback (currently unused; Data API is primary)
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

## v1 intentional limitations

- **No captions = error.** Whisper fallback not implemented; most popular videos have auto-captions so this rarely bites.
- **Single language summary.** Output language matches transcript language. No translation step.
- **Tags are English kebab-case only.** Keeps cross-vault deduplication clean.
- **Self-hosted runner required.** Cloud-provider IPs are blocked by YouTube for transcript scraping.

## Setup checklist (for a fresh fork)

1. ◌ `gh repo fork --clone` (or template-use)
2. ◌ `mv vault.example vault` and commit
3. ◌ GitHub Secrets: `YOUTUBE_API_KEY`, `GEMINI_API_KEY` (use `gcloud → gh secret set` pipeline from README)
4. ◌ Self-hosted runner installed + registered + systemd user service
5. ◌ (Optional) `LOCAL_VAULT_PATH` repo variable set if you want instant local sync
6. ◌ (Optional) Connect `auto_project` Telegram bot for phone-triggered runs
7. ◌ Open `vault/` in Obsidian, install Dataview plugin
8. ◌ (Mobile) Termux + clone, Obsidian Git plugin with required settings (Author name/email MUST be set even with Disable push)

## Self-hosted runner notes

- Service name: `yt-obsidian-runner` (user-level systemd, no sudo for service itself)
- Location: `~/actions-runner/`
- Status: `systemctl --user status yt-obsidian-runner`
- Reboot survival needs `sudo loginctl enable-linger <user>` (one-time sudo prompt)
- Without linger, the runner stops when the user logs out

## Mobile (Android) gotchas

- Vault must be opened at **repo root** (where `.git` is), not `vault/` subdirectory. Obsidian Git on mobile (isomorphic-git) doesn't walk up reliably.
- `Author name for commits` and `Author email for commits` are **required** even when `Disable push` is ON — the plugin refuses to run otherwise.
- Use `Settings → Files & links → Excluded files` to hide non-vault paths (`notes_project/`, `.github/`, `scripts/`, etc.) from Obsidian's file tree.

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
