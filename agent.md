# agent.md

Shared instructions for any AI coding agent working on this repository, including Claude Code, Codex, and Cursor. Claude-specific details are in [CLAUDE.md](CLAUDE.md).

## Mission

Maintain **BlogFlow Studio**, a Windows tool that researches keywords, drafts Korean articles about 정부 지원금 and 생활비 절약, and publishes them to Google Blogger safely.

## Hard rules

1. **Never commit secrets.** That covers `.env`, `credentials.json`, `client_secret*.json`, `token.json`, `connections.sec`, and anything in `BlogFlow-data/`. Run `git status` before committing, and stop if any of these show up.
2. **Never print or log API keys.** Keep the DPAPI encryption (`studio.crypt`) and the `[비공개]` error masking.
3. **Default to draft.** Never make immediate or live publishing the default, and never auto-retry an upload whose outcome is uncertain. See the `state.json` recovery flow in `사용설명서.md`.
4. **Do not invent facts.** Amounts, dates, and eligibility for government programs must come from official sources, with a 기준일. Unverified items say "공식 안내 확인".
5. **Keep the local server private.** It stays bound to `127.0.0.1`, with the per-launch token and Host and Origin checks.
6. **Korean UI and docs.** User-facing strings and documentation stay in Korean.

## Workflow

1. Read the relevant module before editing, and match its compact style. Do not reformat whole files.
2. Keep changes small and focused. Update `사용설명서.md` or `앱-사용법.md` when behavior changes.
3. Verify with `blogger_auto.py preview` or the studio preview. Never publish to a real blog without the user's explicit approval.
4. Build artifacts (`BlogFlow.exe`, `*.zip`, `build/`, `dist/`) go to GitHub Releases, not into git.

## Map

| Area | Files |
|---|---|
| App / UI | `studio.py`, `web/index.html` (legacy: `app.py`) |
| Blogger API | `blogger_auto.py` |
| Research | `research.py` (Naver SearchAd, DataLab) |
| Writing | `content_engine.py`, `writer.py`, `deep_writer.py` |
| Automation | `autopilot.py`, `channels.py`, `naver_handoff.py` |
| Docs | `사용설명서.md`, `앱-사용법.md`, `광고-설정-안내.md` |

## Commit style

Write short imperative messages in Korean or English, for example `fix: 예약 발행 시간대 변환 오류 수정`. Create one logical change per commit.
