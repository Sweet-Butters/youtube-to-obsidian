# youtube-to-obsidian

> YouTube 영상을 구조화된 Obsidian 노트로 자동 변환. 폰에서 URL 보내면 30초 만에 vault에 전문가급 요약이 들어옵니다.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org)
[![Framework](https://img.shields.io/badge/framework-auto__project%20v0.5.0-green.svg)](https://github.com/Sweet-Butters/auto_project)

**언어:** [English](README.md) · 한국어 (이 파일)

---

## 목차

1. [무엇을 하는가](#무엇을-하는가)
2. [아키텍처](#아키텍처)
3. [주요 기능](#주요-기능)
4. [빠른 시작](#빠른-시작)
5. [설정](#설정)
6. [수동 실행](#수동-실행)
7. [폰에서 트리거 (Telegram)](#폰에서-트리거-telegram)
8. [카테고리](#카테고리)
9. [모바일 Obsidian 셋업](#모바일-obsidian-셋업)
10. [문제 해결](#문제-해결)
11. [로드맵](#로드맵)
12. [감사](#감사)
13. [License](#license)

---

## 무엇을 하는가

YouTube URL이 주어지면 이 파이프라인이:

1. **YouTube Data API v3**로 영상 메타데이터 가져옴 (제목, 채널, 길이, 공식 `categoryId` 등).
2. [`youtube-transcript-api`](https://github.com/jdepoix/youtube-transcript-api)로 트랜스크립트 추출 (수동/자동 자막, 언어 자동 감지).
3. [`auto_project.llm`](https://github.com/Sweet-Butters/auto_project)이 라우팅하는 **무료 tier LLM**으로 요약 (Gemini → Groq → Cerebras 폴백).
4. YAML frontmatter (`category_id`, `category_en`, `category_ko`, `tags`, `date_watched` 등) 포함된 **구조화된 마크다운 노트**를 Obsidian vault에 작성.
5. GitHub에 push. 로컬 Obsidian (그리고 옵션으로 폰 Obsidian) 이 몇 초 안에 새 노트 감지.

출력은 **Dataview**로 쿼리 가능 — 본 날짜순 정렬, 카테고리별 그룹핑, 채널별 필터링 등.

## 아키텍처

```
[폰: YouTube → 공유 → Telegram 봇]
    │ URL 메시지
    ▼
[Cloud Run 서비스 (auto_project 봇, URL_ROUTES)]
    │ workflow_dispatch
    ▼
[GitHub Actions — 가정 IP의 셀프호스트 러너]
    │
    ├─ YouTube Data API v3       → 메타데이터 + categoryId
    ├─ youtube-transcript-api    → 자막
    └─ auto_project.llm (무료)    → 요약 + 태그
    │
    ▼
[vault/YouTube/YYYY-MM-DD_slug_[video_id].md 커밋 + push]
    │
    ▼
[로컬 Obsidian (파일 워처) + 폰 Obsidian (Obsidian Git 자동 pull)]
```

셀프호스트 러너가 **필수** — GitHub 호스티드 러너 (Azure IP) 는 YouTube의 anti-scraping 정책에 차단당합니다. 아래 [셀프호스트 러너 셋업](#셀프호스트-러너-셋업) 섹션 참고.

## 주요 기능

- **이중 언어 카테고리 라벨** — 모든 노트가 `category_en` ("Science & Technology") 와 `category_ko` ("과학/기술") 둘 다 저장. frontmatter의 `category` 는 `--lang` 설정에 따라 둘 중 하나를 미러링; 나중에 `scripts/recategorize.py` 로 vault 전체 한 번에 전환 가능.
- **YouTube 공식 카테고리** — Data API의 `categoryId` (15개 카테고리) 사용. LLM 추측 X, 일관성 보장.
- **무료 LLM** — Gemini 무료 tier + Groq, Cerebras 자동 폴백. 유료 API 필요 없음.
- **견고한 JSON 파서** — LLM JSON 모드의 quirks (마크다운 fence, 끝에 붙는 prose, 따옴표 누락) 처리. 파싱 실패 시 1회 자동 재시도.
- **폰에서 트리거** — Telegram 통해 YouTube 링크 공유 → vault에 노트. [`auto_project`의 URL 라우팅](https://github.com/Sweet-Butters/auto_project) (Cloud Run 서비스) 과 연동.
- **Dataview 친화적** — Dataview 쿼리에 최적화된 frontmatter 설계. 샘플 dashboard 포함 (`vault.example/Dashboard.md`).
- **모바일 vault 동기화** — Android Obsidian + Obsidian Git 플러그인이 1분 안에 새 노트 pull.

## 빠른 시작

### 사전 준비물

- Python 3.11+
- 결제 활성화된 GCP 프로젝트 (무료 tier 충분)
- GitHub 계정
- (선택, 권장) 셀프호스트 러너용 WSL2 / Linux 머신

### 1. Fork 또는 clone

```bash
gh repo fork <YOUR_GITHUB_USER>/youtube-to-obsidian --clone
# 또는
git clone https://github.com/<YOUR_GITHUB_USER>/youtube-to-obsidian.git
cd youtube-to-obsidian
```

### 2. API 키 발급 (무료)

**YouTube Data API v3** — `gcloud` CLI 권장 (키가 터미널에 노출되지 않음):

```bash
gcloud services enable youtube.googleapis.com --quiet
KEY_NAME=$(gcloud services api-keys create \
  --display-name="youtube-to-obsidian YouTube" \
  --api-target=service=youtube.googleapis.com \
  --format="value(response.name)" --quiet)
gcloud services api-keys get-key-string "$KEY_NAME" --format="value(keyString)" --quiet \
  | gh secret set YOUTUBE_API_KEY --repo <YOUR_GITHUB_USER>/youtube-to-obsidian
```

**Gemini API** — 동일한 패턴:

```bash
gcloud services enable generativelanguage.googleapis.com --quiet
KEY_NAME=$(gcloud services api-keys create \
  --display-name="youtube-to-obsidian Gemini" \
  --api-target=service=generativelanguage.googleapis.com \
  --format="value(response.name)" --quiet)
gcloud services api-keys get-key-string "$KEY_NAME" --format="value(keyString)" --quiet \
  | gh secret set GEMINI_API_KEY --repo <YOUR_GITHUB_USER>/youtube-to-obsidian
```

또는 GUI 사용: [Google Cloud Console](https://console.cloud.google.com) → APIs & Services → Credentials. GitHub Secrets에 수동 추가.

### 3. Vault 초기화

```bash
mv vault.example vault
git add -A && git commit -m "init: rename vault.example -> vault"
```

`vault/` 디렉터리가 GitHub Actions가 노트를 커밋할 위치입니다.

### 4. 셀프호스트 러너 셋업

**왜 셀프호스트인가**: YouTube가 클라우드 IP (AWS, GCP, Azure, **GitHub 호스티드 러너**) 의 자막 스크래핑을 차단. 가정 IP는 작동.

파이프라인을 돌릴 머신에서 (Linux / WSL2 권장):

```bash
mkdir -p ~/actions-runner && cd ~/actions-runner

# 최신 러너 버전 확인
RUNNER_VERSION=$(curl -s https://api.github.com/repos/actions/runner/releases/latest \
  | grep -oP '"tag_name":\s*"v\K[^"]+')

curl -L -o runner.tar.gz \
  "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz"
tar xzf runner.tar.gz

# 등록 (gh CLI로 registration token 발급)
TOKEN=$(gh api -X POST /repos/<YOUR_GITHUB_USER>/youtube-to-obsidian/actions/runners/registration-token --jq .token)
./config.sh \
  --url https://github.com/<YOUR_GITHUB_USER>/youtube-to-obsidian \
  --token "$TOKEN" \
  --name my-runner \
  --labels self-hosted,linux \
  --unattended --replace
```

User-level systemd 서비스로 실행 (서비스 자체엔 sudo 필요 없음; 재부팅 후 자동 시작은 `sudo loginctl enable-linger` 필요):

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

GitHub 레포 → Settings → Actions → Runners 에서 러너가 online으로 표시되는지 확인.

### 5. 첫 실행 트리거

```bash
gh workflow run summarize-video.yml \
  -f url="https://www.youtube.com/watch?v=jNQXAC9IVRw" \
  -f display_lang=ko \
  --repo <YOUR_GITHUB_USER>/youtube-to-obsidian
```

약 30초 후 `vault/YouTube/` 에서 새 노트 확인.

### 6. Obsidian에서 열기

[Obsidian](https://obsidian.md) (데스크탑 또는 모바일) 에서 `vault/` 폴더를 vault로 엽니다. **Dataview** 커뮤니티 플러그인 설치하면 `Dashboard.md`가 렌더링됩니다.

## 설정

### GitHub Secrets (workflow에 필수)

| Secret | 출처 |
|---|---|
| `YOUTUBE_API_KEY` | GCP → APIs & Services → YouTube Data API v3 |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/apikey) (무료) |
| `GROQ_API_KEY` | (선택) [Groq Cloud](https://console.groq.com) — fallback LLM |
| `CEREBRAS_API_KEY` | (선택) [Cerebras Cloud](https://cloud.cerebras.ai) — fallback LLM |
| `TELEGRAM_BOT_TOKEN` | (선택) [@BotFather](https://t.me/BotFather) — 폰 트리거용 |
| `TELEGRAM_CHAT_ID` | (선택) 본인 chat ID |

### Repository variables (선택)

| Variable | 용도 |
|---|---|
| `LOCAL_VAULT_PATH` | 셀프호스트 러너 머신에 있는 본 레포의 로컬 클론 절대 경로. 설정 시 매 push 후 workflow가 `git pull` 해서 로컬 Obsidian vault가 즉시 새 노트 인식. 예: `/home/<YOUR_USER>/youtube-to-obsidian` |

## 수동 실행

로컬 개발이나 일회성 요약:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .

export YOUTUBE_API_KEY=<YOUR_KEY>
export GEMINI_API_KEY=<YOUR_KEY>

.venv/bin/python -m notes_project "https://youtu.be/VIDEO_ID" --lang ko
# → vault/YouTube/YYYY-MM-DD_slug_[VIDEO_ID].md 생성
```

표시 언어는 `ko` (한글) 또는 `en` 가능.

## 폰에서 트리거 (Telegram)

본 파이프라인은 [`auto_project`](https://github.com/Sweet-Butters/auto_project) 의 Telegram 봇 (Cloud Run 서비스) 과 연동합니다. 봇의 `URL_ROUTES` 환경변수 설정:

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

이제 봇한테 YouTube URL 공유하면 workflow가 자동 발동. Cloud Run 전체 배포는 `auto_project`의 [`bot/README.md`](https://github.com/Sweet-Butters/auto_project/blob/main/bot/README.md) 참고.

## 카테고리

파이프라인은 YouTube Data API의 공식 `categoryId`를 사용. 모든 노트 frontmatter에 영문/한글 라벨 둘 다 저장:

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

알 수 없는 카테고리는 `Uncategorized` / `기타`로 폴백. 매핑은 [`auto_project/youtube/categories.py`](https://github.com/Sweet-Butters/auto_project/blob/main/src/auto_project/youtube/categories.py) 에 정의.

### 재분류

```bash
# 모든 노트의 표시 언어 전환 (ko → en):
python scripts/recategorize.py vault/YouTube --display-lang en

# 한 노트의 카테고리 수동 변경:
python scripts/recategorize.py vault/YouTube/<note>.md --new-category "교육"
```

또는 Obsidian에서 `category:` frontmatter 필드를 직접 편집해도 됩니다.

## 모바일 Obsidian 셋업

폰 (Android) 에서 노트 보려면 [Obsidian Git](https://github.com/Vinzent03/obsidian-git) 사용:

1. **Fine-grained Personal Access Token 발급** — 본 레포 한정, `Contents: Read-only` 권한 (본 템플릿은 public이지만 private fork 시 PAT 필요).
2. **Termux 설치** + Obsidian 설치. Termux로 clone:
   ```bash
   termux-setup-storage
   pkg install -y git
   cd ~/storage/shared
   PAT=<YOUR_PAT>
   git clone "https://<YOUR_GITHUB_USER>:${PAT}@github.com/<YOUR_GITHUB_USER>/youtube-to-obsidian.git"
   ```
3. **Obsidian 실행** → "Open folder as vault" → **레포 루트** 선택 (`vault/` 하위 폴더 아님 — Obsidian Git이 모바일에서 vault 루트에 `.git` 있어야 작동).
4. **Obsidian Git 플러그인 설치** (Settings → Community plugins). 필수 설정:
   - Auto pull interval (minutes): `1`
   - Pull on startup: ON
   - Disable push: ON
   - Auto commit-and-sync interval: `0`
   - **Author name / Author email**: 아무 값이든 채워넣어야 함 — 비어있으면 Obsidian Git 명령 자체가 실행 안 됨.
5. **vault 외 파일 숨기기** — Settings → Files & links → Excluded files 에 추가: `notes_project/`, `.github/`, `scripts/`, `tests/`, `*.py`, `*.toml`, `*.txt`.

## 문제 해결

| 문제 | 해결 |
|---|---|
| `RequestBlocked: YouTube is blocking requests from your IP` | 클라우드 제공자 IP에서 실행 중. 가정 IP의 셀프호스트 러너 사용, 또는 residential 프록시 추가 (예: WebShare 무료 tier — `youtube-transcript-api`에 `WebshareProxyConfig` 내장). |
| `ModuleNotFoundError: No module named 'auto_project.youtube'` | Stale pip 캐시. `pyproject.toml`이 `auto_project @ git+...@v0.5.0` 핀하는지 확인 (v0.4.0 아님). Workflow가 매 실행마다 fresh venv 만들어서 깨끗한 push로 해결됨. |
| `LookupError: No usable captions for video` | 영상에 자막 없음. v1은 Whisper 폴백 미지원 — 다른 영상 시도하거나, fork 후 `fetch_transcript`에 `faster-whisper` 추가. |
| 모바일 Obsidian Git: "명령은 있는데 실행 안 됨" | Author name/email 필드 비어있음. 아무 값이든 채워넣기 — `Disable push` 켜져있어도 필수. |
| 노트가 repo엔 있는데 Obsidian엔 안 보임 | 로컬 클론이 pull 안 됨. `LOCAL_VAULT_PATH` repo 변수 설정 (랩탑) 또는 Obsidian Git 자동 pull 활성화 확인 (폰). |
| Summarize 단계에서 `JSONDecodeError` | LLM이 잘못된 JSON 반환. 파이프라인이 1회 자동 재시도하지만, 그래도 실패하면 timeout 늘리거나 `GEMINI_API_KEY` 유효성 확인. |

## 로드맵

- [ ] 트랜스크립트 fetch용 WebShare 프록시 폴백 (GitHub 호스티드 러너도 백업으로 작동)
- [ ] 자막 없는 영상에 대한 Whisper 기반 전사 (opt-in, OpenAI 또는 로컬 모델 유료)
- [ ] 추가 콘텐츠 타입: arXiv 논문, 웹 기사 ([`defuddle`](https://github.com/spaceage64/claude-defuddle) 통해), Apple 팟캐스트
- [ ] 다중 사용자 / 다중 vault 지원
- [ ] vault 전체 태그 중복제거 자동화

## 감사

본 프로젝트는 다음 위에 서 있습니다:

- [`auto_project`](https://github.com/Sweet-Butters/auto_project) — LLM 라우터, state, Telegram 봇을 제공하는 framework.
- [`JimmySadek/youtube-fetcher-to-markdown`](https://github.com/JimmySadek/youtube-fetcher-to-markdown) — 파일명 컨벤션과 frontmatter 설계 차용.
- [`spaceage64/claude-defuddle`](https://github.com/spaceage64/claude-defuddle) — subprocess 기반 추출 패턴 (토큰 효율).
- [`Stnslv-k/shorts-saver-bot`](https://github.com/Stnslv-k/shorts-saver-bot) — Telegram → Obsidian 아키텍처와 트랜스크립트 폴백 로직.
- [`tuan3w/obsidian-vault-agent`](https://github.com/tuan3w/obsidian-vault-agent) — Zettelkasten 규칙과 "vault용 에이전트" 비전.
- [`Vinzent03/obsidian-git`](https://github.com/Vinzent03/obsidian-git) — 모바일 동기화를 가능케 하는 Obsidian 플러그인.

## License

[MIT](LICENSE)
