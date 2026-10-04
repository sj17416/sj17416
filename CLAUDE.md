# CLAUDE.md

This file gives Claude Code (and other coding agents) the context needed to work in this repository. Agent-neutral rules are also in [agent.md](agent.md). Keep the two files consistent.

## Project overview

BlogFlow Studio is a Windows desktop tool that automates a Korean monetized blog on Google Blogger (Blogspot). Its main topics are 정부 지원금 and 생활비 절약. It handles keyword research, article drafting, AdSense ad slot placement, and publishing to Blogger (draft, scheduled, or immediate). It can also share posts to SNS and produce a Naver blog handoff.

All user-facing text, docs, and UI are in **Korean**.

## Entry points

| File | What it is |
|---|---|
| `studio.py` | **Main app (BlogFlow.exe entry).** It runs a local HTTP server bound to `127.0.0.1` with a random per-launch token, serves `web/index.html`, and opens Edge in app mode. All actions go through `action(name, payload)`. |
| `app.py` | Legacy Tkinter publishing helper, started by `앱-실행.cmd`. |
| `blogger_auto.py` | Blogger API v3 engine and CLI: OAuth, `blogs`, `preview`, `run`. It is idempotent through `state.json`. |
| `web/index.html` | Single-file front end for the studio. |

## Modules

- `research.py`: Naver SearchAd keyword tool, Naver DataLab trends, and monthly keyword research with CSV metric import. `request_json()` is the shared HTTP helper.
- `content_engine.py`: Offline topic table (official source URLs per topic), draft templates, `seo_review()`.
- `writer.py`: Builds articles. `offline_article()` needs no key. `ai_article()` calls the OpenAI Responses API. `validate()` and `render()` produce the Blogger HTML with ad slots.
- `deep_writer.py`: Two-step AI writing: `investigate()` does research, then `deep_article()` writes, then `quality()` checks.
- `autopilot.py`: Scheduled pipeline: `prepare`, `deliver`, `tick`.
- `channels.py`: Posting to Threads, Facebook Page, and X, plus `summaries()`.
- `naver_handoff.py`: Packages an article for manual pasting into Naver Blog, which has no write API.

## Run (development)

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe studio.py          # web studio
.\.venv\Scripts\python.exe blogger_auto.py blogs  # CLI: list blogs
```

## Build (EXE)

The app is built with PyInstaller as a one-folder build named `BlogFlow`, from `studio.py`, bundling `logo.png` and `web/` plus `googleapiclient` discovery data. Hidden imports are `google_auth_oauthlib.flow` and `googleapiclient.discovery`. `*.spec`, `build/`, `dist/`, `*.exe`, and `*.zip` are git-ignored. Attach release zips to **GitHub Releases** and never commit them.

## Data and secrets (critical)

- Runtime data lives in `BlogFlow-data/`. That folder sits next to the EXE when frozen, or next to `studio.py` in dev. `BLOGFLOW_DATA_DIR` overrides the location.
- API keys are stored in `BlogFlow-data/connections.sec`, **encrypted with Windows DPAPI** (`crypt()` in `studio.py`). The allowed key names are in `save_keys()`. Never write keys in plain text, never log them, and keep the `[비공개]` masking in `task()` and `autopilot.clean_error()`.
- `credentials.json` (OAuth desktop client), `token.json`, `state.json`, `.env`, and `connections.sec` must never be committed. `.gitignore` covers them. Check `git status` before every commit.

## Conventions

- Python 3.10+ uses the standard library where possible. Code style is compact, and many modules use `;`-joined statements. Match the surrounding style and do not reformat whole files.
- All file I/O is UTF-8. Paths may contain Korean characters, so use `pathlib`.
- Blogger publishing defaults to **draft**. Never change a default to auto-publish live.
- Keep the idempotency and recovery logic in `blogger_auto.run()` and `state.json`. Do not auto-retry an upload whose result is uncertain.
- The local server must stay bound to `127.0.0.1` with the token, Host, and Origin checks in `Handler`.

## Content rules (YMYL)

Government-benefit articles are YMYL content. Generated or edited content must:
- cite official sources (gov.kr, bokjiro.go.kr, energyv.or.kr, nts.go.kr, …) and show the 기준일,
- never invent amounts, dates, or eligibility rules. If something is unverified, say "공식 안내 확인",
- keep the "정부 공식 사이트가 아닙니다" disclaimer,
- keep ad slots clearly separated from CTA buttons, to follow AdSense accidental-click policy.

## Testing

There is no test suite in this repo yet. Earlier ad-hoc tests (`test_studio.py`, `test_automation.py`) live outside the repo. Run `blogger_auto.py preview` and the studio's preview before any real publish. Real Google, OpenAI, and Naver calls need the user's own credentials.
