# youtube-to-obsidian

> Turn any YouTube video into a structured, searchable Obsidian note — automatically. Send a URL from your phone, get a professional summary in your vault 30 seconds later.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org)
[![Framework](https://img.shields.io/badge/framework-auto__project%20v0.5.0-green.svg)](https://github.com/Sweet-Butters/auto_project)

**Languages:** English (this file) · [한국어](README.ko.md)

---

## Table of contents

1. [What it does](#what-it-does)
2. [Architecture](#architecture)
3. [Features](#features)
4. [Quick start](#quick-start)
5. [Configuration](#configuration)
6. [Manual run](#manual-run)
7. [Phone-triggered runs (Telegram)](#phone-triggered-runs-telegram)
8. [Categories](#categories)
9. [Mobile Obsidian setup](#mobile-obsidian-setup)
10. [Common pitfalls (mobile)](#common-pitfalls-mobile)
11. [Troubleshooting](#troubleshooting)
12. [Roadmap](#roadmap)
13. [Acknowledgments](#acknowledgments)
14. [License](#license)

---

## What it does

Given a YouTube URL, this pipeline:

1. Fetches the video's metadata via the **YouTube Data API v3** (title, channel, duration, official `categoryId`, etc.).
2. Pulls the transcript via [`youtube-transcript-api`](https://github.com/jdepoix/youtube-transcript-api) (manual or auto-generated captions, language-aware).
3. Summarizes with a **free-tier LLM** routed through [`auto_project.llm`](https://github.com/Sweet-Butters/auto_project) (Gemini → Groq → Cerebras fallback).
4. Writes a **structured Markdown note** with YAML frontmatter (`category_id`, `category_en`, `category_ko`, `tags`, `date_watched`, etc.) into your Obsidian vault.
5. Pushes to GitHub. Your local Obsidian (and optionally phone Obsidian) sees the new note within seconds.

The output is queryable with **Dataview** — sort by date watched, group by category, filter by channel, etc.

## Architecture

```
[Phone: YouTube → Share → Telegram bot]
    │ URL message
    ▼
[Cloud Run service (auto_project bot, URL_ROUTES)]
    │ checks runner status, picks fast or fallback workflow
    │ workflow_dispatch
    ▼
┌──────────────────────────────────────┬──────────────────────────────────────┐
│   FAST PATH (self-hosted online)     │   FALLBACK PATH (self-hosted offline)│
│   runs-on: [self-hosted, linux]      │   runs-on: ubuntu-latest             │
│                                      │                                      │
│   Direct IP (residential, home)      │   WebShare residential proxy         │
│   • youtube-transcript-api (direct)  │   • youtube-transcript-api (proxy)   │
│   • Whisper local fallback (free)    │   • Whisper disabled (CI minutes)    │
│   ~30-45s end-to-end                 │   ~40-60s, best-effort on free proxy │
└──────────────────────┬───────────────┴────────────────┬─────────────────────┘
                       │                                │
                       │   Either path:                 │
                       ▼                                ▼
        ┌─────────────────────────────────────────────────────┐
        │ • YouTube Data API v3        → metadata + categoryId│
        │ • Transcript fetch (one of the two paths above)     │
        │ • vault_indexer              → backlink context     │
        │ • auto_project.llm (Gemini)  → summary + tags +     │
        │                                [[wikilinks]]        │
        │ • vault/YouTube/...md commit + push                 │
        └─────────────────────────────┬───────────────────────┘
                                      ▼
        [Local Obsidian (file watcher) + Phone Obsidian (Obsidian Git pull)]
```

The `auto_project` bot (≥ v0.6.0) calls `GET /repos/{owner}/{repo}/actions/runners` before dispatch and picks the workflow that will actually run — so the user always gets a result, whether the home machine is on or not.

> **Why two paths?** YouTube blocks the unofficial caption scrape from cloud-provider IPs (AWS, GCP, Azure, **GitHub-hosted runners**). The self-hosted runner solves this by running on a residential IP. The fallback path keeps the pipeline alive while the on-prem machine is sleeping, using a residential proxy instead.

## Features

- **Always-on hybrid execution** (v0.2.0+) — the bot picks between a fast self-hosted path (residential IP, Whisper enabled, ~30s) and a hosted-runner fallback path (WebShare proxy, ~50s) based on runner availability. Removes the "laptop must be on" limitation of v0.1.x.
- **Caption-less videos handled** (v0.2.0+) — when the self-hosted runner is the executor, `faster-whisper` transcribes the audio locally when no captions exist. Free, offline, CPU-only.
- **Automatic Zettelkasten backlinks** (v0.2.0+) — the LLM is fed the 50 most-recent vault notes as context and embeds `[[exact title]]` wikilinks where topically related. The knowledge graph grows organically.
- **Bilingual category labels** — every note stores both `category_en` ("Science & Technology") and `category_ko` ("과학/기술"). Frontmatter `category` mirrors one based on your `--lang` setting; flip across the whole vault later with `scripts/recategorize.py`.
- **YouTube official categories** — uses Data API's `categoryId` (15 categories) for authoritative classification. No LLM guessing.
- **Zero-cost LLM** — Gemini free tier with automatic Groq and Cerebras fallback. No paid API needed.
- **Robust JSON parsing** — handles LLM JSON-mode quirks (markdown fences, trailing prose, unbalanced quotes). One automatic retry on parse failure.
- **Phone-triggered** — share a YouTube link from your phone via Telegram, get a note in your vault. Works with [`auto_project`'s URL routing](https://github.com/Sweet-Butters/auto_project) (Cloud Run service).
- **Dataview-ready** — frontmatter designed for Dataview queries. Sample dashboard included (`vault.example/Dashboard.md`).
- **Mobile vault sync** — Android Obsidian + Obsidian Git plugin pulls notes within 1 minute.

## Quick start

### Prerequisites

- Python 3.11+
- A GCP project with billing enabled (free tier is fine)
- A GitHub account
- (Optional, recommended) A WSL2 / Linux machine for the self-hosted runner

### 1. Fork or clone

```bash
gh repo fork <YOUR_GITHUB_USER>/youtube-to-obsidian --clone
# or
git clone https://github.com/<YOUR_GITHUB_USER>/youtube-to-obsidian.git
cd youtube-to-obsidian
```

### 2. Get your API keys (free)

**YouTube Data API v3** — via `gcloud` CLI (recommended, key never appears in your terminal):

```bash
gcloud services enable youtube.googleapis.com --quiet
KEY_NAME=$(gcloud services api-keys create \
  --display-name="youtube-to-obsidian YouTube" \
  --api-target=service=youtube.googleapis.com \
  --format="value(response.name)" --quiet)
gcloud services api-keys get-key-string "$KEY_NAME" --format="value(keyString)" --quiet \
  | gh secret set YOUTUBE_API_KEY --repo <YOUR_GITHUB_USER>/youtube-to-obsidian
```

**Gemini API** — same pattern:

```bash
gcloud services enable generativelanguage.googleapis.com --quiet
KEY_NAME=$(gcloud services api-keys create \
  --display-name="youtube-to-obsidian Gemini" \
  --api-target=service=generativelanguage.googleapis.com \
  --format="value(response.name)" --quiet)
gcloud services api-keys get-key-string "$KEY_NAME" --format="value(keyString)" --quiet \
  | gh secret set GEMINI_API_KEY --repo <YOUR_GITHUB_USER>/youtube-to-obsidian
```

Or use the GUI: [Google Cloud Console](https://console.cloud.google.com) → APIs & Services → Credentials. Add to GitHub Secrets manually.

### 3. Initialize the vault

```bash
mv vault.example vault
git add -A && git commit -m "init: rename vault.example -> vault"
```

The `vault/` directory is what GitHub Actions will commit notes into.

### 4. Self-hosted runner setup

**Why self-hosted**: YouTube blocks cloud-provider IPs (AWS, GCP, Azure, **GitHub-hosted runners**) from caption scraping. Your home IP works.

On the machine you want to run the pipeline on (Linux / WSL2 recommended):

```bash
mkdir -p ~/actions-runner && cd ~/actions-runner

# Get the latest runner version
RUNNER_VERSION=$(curl -s https://api.github.com/repos/actions/runner/releases/latest \
  | grep -oP '"tag_name":\s*"v\K[^"]+')

curl -L -o runner.tar.gz \
  "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz"
tar xzf runner.tar.gz

# Register (get registration token via gh CLI)
TOKEN=$(gh api -X POST /repos/<YOUR_GITHUB_USER>/youtube-to-obsidian/actions/runners/registration-token --jq .token)
./config.sh \
  --url https://github.com/<YOUR_GITHUB_USER>/youtube-to-obsidian \
  --token "$TOKEN" \
  --name my-runner \
  --labels self-hosted,linux \
  --unattended --replace
```

Run as a user-level systemd service (no sudo required for the service itself; reboot survival needs `sudo loginctl enable-linger`):

```bash
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/yt-obsidian-runner.service <<EOF
[Unit]
Description=GitHub Actions Runner (youtube-to-obsidian)
After=network-online.target

[Service]
Type=simple
WorkingDirectory=$HOME/actions-runner
ExecStart=$HOME/actions-runner/run.sh
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now yt-obsidian-runner
```

Verify online: GitHub repo → Settings → Actions → Runners.

### 5. Trigger your first run

```bash
gh workflow run summarize-video.yml \
  -f url="https://www.youtube.com/watch?v=jNQXAC9IVRw" \
  -f display_lang=ko \
  --repo <YOUR_GITHUB_USER>/youtube-to-obsidian
```

After ~30 seconds, check `vault/YouTube/` for the new note.

### 6. Open in Obsidian

Open the `vault/` folder in [Obsidian](https://obsidian.md) (Desktop or Mobile). Install the **Dataview** community plugin to render `Dashboard.md`.

## Configuration

### GitHub Secrets

| Secret | Source | Required? |
|---|---|---|
| `YOUTUBE_API_KEY` | GCP → APIs & Services → YouTube Data API v3 | yes |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/apikey) (free) | yes |
| `WEBSHARE_USER` | [WebShare](https://www.webshare.io) → Proxy → Username (residential proxy auth) | **for fallback path only** |
| `WEBSHARE_PASS` | WebShare → Proxy → Password | **for fallback path only** |
| `GROQ_API_KEY` | [Groq Cloud](https://console.groq.com) — secondary LLM | optional |
| `CEREBRAS_API_KEY` | [Cerebras Cloud](https://cloud.cerebras.ai) — tertiary LLM | optional |
| `TELEGRAM_BOT_TOKEN` | [@BotFather](https://t.me/BotFather) | optional (phone triggers) |
| `TELEGRAM_CHAT_ID` | Your chat ID | optional (phone triggers) |

If you only run the self-hosted fast path you can skip `WEBSHARE_*` entirely — the fallback workflow simply won't have what it needs to run, and the bot will never dispatch it as long as your runner is online.

### Repository variables (optional)

| Variable | Purpose |
|---|---|
| `LOCAL_VAULT_PATH` | Absolute path to a local clone of this repo on the self-hosted runner machine. When set, the workflow `git pull`s after each push so a local Obsidian vault sees the new note instantly. Example: `/home/<YOUR_USER>/youtube-to-obsidian` |

### Workflow-level env vars (no secret needed)

The pipeline reads several env vars set directly in workflow YAML, not from secrets:

| Variable | Where it's set | Purpose |
|---|---|---|
| `ENABLE_WHISPER=1` | `summarize-video.yml` (fast path only) | Activates local `faster-whisper` transcription for caption-less videos. Disabled on the fallback workflow to save CI minutes. |
| `WHISPER_MODEL=base` | `summarize-video.yml` | Model size — `tiny`/`base`/`small`/`medium`/`large-v3`. Bigger = more accurate, slower, more disk. |

## Manual run

For local development or one-off summarization:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .

export YOUTUBE_API_KEY=<YOUR_KEY>
export GEMINI_API_KEY=<YOUR_KEY>

.venv/bin/python -m notes_project "https://youtu.be/VIDEO_ID" --lang ko
# → writes vault/YouTube/YYYY-MM-DD_slug_[VIDEO_ID].md
```

Display language can be `ko` (한글) or `en`.

## Phone-triggered runs (Telegram)

This pipeline pairs with [`auto_project`](https://github.com/Sweet-Butters/auto_project)'s Telegram bot (Cloud Run service). Configure the bot's `URL_ROUTES` env var:

```yaml
URL_ROUTES: |
  [
    {
      "pattern": "(?:youtube\\.com/watch|youtu\\.be/)",
      "repo": "<YOUR_GITHUB_USER>/youtube-to-obsidian",
      "workflow": "summarize-video.yml",
      "input_key": "url",
      "extra_inputs": {"display_lang": "ko"}
    }
  ]
```

Now share any YouTube URL to the bot and the workflow fires automatically. See `auto_project`'s [`bot/README.md`](https://github.com/Sweet-Butters/auto_project/blob/main/bot/README.md) for full Cloud Run deployment.

## Categories

The pipeline uses YouTube Data API's official `categoryId`. Both English and Korean labels are stored in every note's frontmatter:

| `categoryId` | `category_en` | `category_ko` |
|---|---|---|
| 1 | Film & Animation | 영화/애니메이션 |
| 2 | Autos & Vehicles | 자동차 |
| 10 | Music | 음악 |
| 15 | Pets & Animals | 반려동물/동물 |
| 17 | Sports | 스포츠 |
| 19 | Travel & Events | 여행/행사 |
| 20 | Gaming | 게임 |
| 22 | People & Blogs | 사람/블로그 |
| 23 | Comedy | 코미디 |
| 24 | Entertainment | 엔터테인먼트 |
| 25 | News & Politics | 뉴스/정치 |
| 26 | Howto & Style | 하우투/스타일 |
| 27 | Education | 교육 |
| 28 | Science & Technology | 과학/기술 |
| 29 | Nonprofits & Activism | 비영리/사회운동 |

Unknown categories fall back to `Uncategorized` / `기타`. The mapping lives in [`auto_project/youtube/categories.py`](https://github.com/Sweet-Butters/auto_project/blob/main/src/auto_project/youtube/categories.py).

### Re-categorize

```bash
# Flip every note's display language (ko → en):
python scripts/recategorize.py vault/YouTube --display-lang en

# Force one note's category manually:
python scripts/recategorize.py vault/YouTube/<note>.md --new-category "Education"
```

Or just edit the `category:` frontmatter field directly in Obsidian.

## Mobile Obsidian setup

> Heads-up: mobile Obsidian Git has a few non-obvious pitfalls that are worth
> reading before you start. See [Common pitfalls (mobile)](#common-pitfalls-mobile)
> below for the symptoms we hit, the causes, and the fixes.

To see notes on your phone (Android), use [Obsidian Git](https://github.com/Vinzent03/obsidian-git):

1. **Create a fine-grained Personal Access Token** scoped to your repo, `Contents: Read-only` (this template is public but if you fork as private the PAT is needed).
2. **Install Termux** + Obsidian on your phone, clone via Termux:
   ```bash
   termux-setup-storage
   pkg install -y git
   cd ~/storage/shared
   PAT=<YOUR_PAT>
   git clone "https://<YOUR_GITHUB_USER>:${PAT}@github.com/<YOUR_GITHUB_USER>/youtube-to-obsidian.git"
   ```
3. **Open Obsidian** → "Open folder as vault" → select **the repo root** (not the `vault/` subfolder — Obsidian Git on mobile needs `.git` at the vault root).
4. **Install Obsidian Git** plugin (Settings → Community plugins). Required settings:
   - Auto pull interval (minutes): `1`
   - Pull on startup: ON
   - Disable push: ON
   - Auto commit-and-sync interval: `0`
   - **Author name / Author email**: must be filled in (any value) — Obsidian Git refuses to run otherwise.
5. **Exclude non-vault files** so Obsidian only shows the markdown notes:
   Settings → Files & links → Excluded files: add `notes_project/`, `.github/`, `scripts/`, `tests/`, `*.py`, `*.toml`, `*.txt`.

## Common pitfalls (mobile)

These three tripped us up during initial setup. Capturing them here so they don't trip you up:

### 1. "Git: Pull" appears in the command palette but tapping it does nothing

**Symptom**: You install Obsidian Git, find or pin **Git: Pull** in the command palette, tap it, and… nothing happens. No toast, no error, no log entry. The plugin appears to load fine, but every git command is a no-op.

**Cause**: Obsidian Git refuses to perform *any* git operation — even read-only ones like `pull` — until the **author identity** is configured. This is true even when `Disable push` is enabled, which is counterintuitive (you'd think no commits = no author needed).

**Fix**: Settings → **Obsidian Git** → fill in **both**:

- *Author name for commits*: any string (e.g. `phone-readonly`)
- *Author email for commits*: any email (e.g. `<YOUR_EMAIL>`)

Save. Re-tap **Git: Pull** — it now runs.

### 2. Finding the sync trigger on mobile

Unlike desktop, mobile Obsidian doesn't show a sync icon by default. Four ways to trigger a pull, in increasing convenience:

| Method | How |
|---|---|
| Command palette (default) | Tap the **⌘ / search icon** in the top bar (or swipe down) → type `pull` → tap **Obsidian Git: Pull** |
| Left sidebar (ribbon) | Swipe from the **left edge** of the screen → tap the Git icon Obsidian Git adds to the ribbon |
| Mobile toolbar (1-tap) | Settings → **Appearance** → **Manage toolbar** → add the `Obsidian Git: Pull` command. Now it's one tap on the note toolbar. |
| App restart | Close + reopen the app. `Pull on startup` (in plugin settings) runs a pull automatically. |

### 3. Subdirectory vault doesn't see the parent `.git`

**Symptom**: You clone the repo into `~/storage/shared/youtube-to-obsidian/`, then open `youtube-to-obsidian/vault/` as the Obsidian vault. Obsidian Git settings show "Not a git repository", or commands fail with "no git repo found".

**Cause**: Obsidian Git on mobile uses `isomorphic-git`, which does not reliably walk up the directory tree to find a parent `.git` on Android's scoped-storage filesystem.

**Fix**: Open the **repository root** (`youtube-to-obsidian/`) as your vault, not the `vault/` subfolder. Then hide non-vault files so they don't clutter the file tree:

Settings → **Files & links** → **Excluded files** → add:

```
notes_project/
.github/
scripts/
tests/
*.py
*.toml
*.txt
.env.example
.gitignore
```

You'll only see `vault/`, `README.md`, `CLAUDE.md`, `CHANGELOG.md`, and `LICENSE` in the file tree — clean and focused.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `RequestBlocked: YouTube is blocking requests from your IP` | You're running on a cloud-provider IP. Use a self-hosted runner on a residential IP, or add a residential proxy (e.g. WebShare free tier — `youtube-transcript-api` has built-in `WebshareProxyConfig`). |
| `ModuleNotFoundError: No module named 'auto_project.youtube'` | Stale pip cache. Make sure `pyproject.toml` pins `auto_project @ git+...@v0.5.0` (not v0.4.0). The workflow creates a fresh venv each run, so a clean push should fix it. |
| `LookupError: No usable captions for video` | The video has no captions at all. v1 doesn't support Whisper fallback — share a different video, or fork and add `faster-whisper` to `fetch_transcript`. |
| Obsidian Git on mobile: "command exists but won't run" | Author name/email fields are empty. Fill them in (any value) — required even with `Disable push` enabled. |
| Note shows up in repo but not in Obsidian | Local clone isn't being pulled. Either set `LOCAL_VAULT_PATH` repo variable (laptop) or check Obsidian Git auto-pull is enabled (phone). |
| `JSONDecodeError` in summarize step | The LLM returned malformed JSON. The pipeline retries once automatically — if it still fails, increase the timeout or check `GEMINI_API_KEY` is valid. |

## Roadmap

- [ ] WebShare proxy fallback for transcript fetch (so GitHub-hosted runners work as backup)
- [ ] Whisper-based transcription for videos without captions (opt-in, paid via OpenAI or local model)
- [ ] Additional content types: arXiv papers, web articles (via [`defuddle`](https://github.com/spaceage64/claude-defuddle)), Apple podcasts
- [ ] Multi-user / multi-vault support
- [ ] Auto-tag deduplication across the vault

## Acknowledgments

This project stands on the shoulders of:

- [`auto_project`](https://github.com/Sweet-Butters/auto_project) — the framework providing the LLM router, state, and Telegram bot.
- [`JimmySadek/youtube-fetcher-to-markdown`](https://github.com/JimmySadek/youtube-fetcher-to-markdown) — filename convention and frontmatter design borrowed.
- [`spaceage64/claude-defuddle`](https://github.com/spaceage64/claude-defuddle) — subprocess-based extraction pattern for token efficiency.
- [`Stnslv-k/shorts-saver-bot`](https://github.com/Stnslv-k/shorts-saver-bot) — Telegram → Obsidian architecture and transcript fallback logic.
- [`tuan3w/obsidian-vault-agent`](https://github.com/tuan3w/obsidian-vault-agent) — Zettelkasten conventions and the broader "agent for your vault" vision.
- [`Vinzent03/obsidian-git`](https://github.com/Vinzent03/obsidian-git) — the Obsidian plugin that makes mobile sync work.

## License

[MIT](LICENSE)
