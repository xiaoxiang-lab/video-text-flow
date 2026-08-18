# video-text-flow · Video Text Production Pipeline (Private Repo)

> 中文：见 [README.md](README.md)。This is the English quick guide.

**In one line**: source material (copy/titles/data) → stance alignment → storyboard draft →
narration finalization → cover → shot job card → voxvideo asset package
(per-shot prompts + reference images + voiceover) → human shoots the video.

Quality assurance: **programmatic checks (deterministic) + constrained sub-agents (semantics)
+ user decisions** — three layers against drift. If it can be programmed, don't use an LLM:
an LLM executing rules is probabilistic reinterpretation; a program is translated once,
executed N times.

## What's in this repo

| Directory | What it is | Runtime location (this machine) |
|---|---|---|
| `checks/` | Programmatic checkers (run_all one-shot; 167 tests) | `C:\Users\xx\Documents\video-text-flow\checks\` |
| `docs/` | Rule docs, 21-style mapping/prompts/rating table, review checklist | same |
| `scripts/` | merge-video, review-images (MiMo 8-dim), style-board review, grid build, Agnes batch gen | same |
| `skills/` | Skill snapshots (whitelist-synced from global skills, **fonts excluded**) | self-contained copy; runtime uses global skills |
| `vendor/` | srt-vox-director upstream snapshot (reference only, see VENDOR-NOTICE) | same |
| `voxvideo/` | VOX asset-package program (src/config/ref/tests + CLAUDE.md + .claude/vox-prompts) | runtime lives in `C:\Users\xx\Documents\Default Project\` |

## Getting started on a new agent (same machine, clone and go)

1. `git clone <repo-url>` anywhere (suggested: `C:\Users\xx\Documents\video-text-flow`).
2. External dependencies are already installed on this machine — no reinstall needed:
   - Global skills at `C:\Users\xx\.config\opencode\skills\` (runtime source of truth;
     the repo `skills/` is only a snapshot — after editing global skills run
     `python checks/sync_skills.py --apply`)
   - Runtime program at `C:\Users\xx\Documents\Default Project\` (voxvideo is deployed
     there; repo `voxvideo/` is a full copy for restore/reference)
   - Python + PIL, 7-Zip, git, ffmpeg, WSL (faster-whisper / Qwen3-TTS) all installed
3. API keys: see below — at most ask the user once.
4. Verify baseline: `python -m unittest discover -s checks/tests -t checks` (167 pass) +
   `python checks/check_docs.py` (0 issues) + `python checks/sync_skills.py` (all same).

## Keys and models (NOT in the repo, user fills in)

- `.env` keys (live in `Default Project\.env`, **never committed**):
  - `AGNES_API_KEY` (Agnes image generation)
  - `MIMO_API_KEY` (MiMo vision/ASR/TTS, token-plan)
  - `FISH_API_KEY` / `FISH_VOICE_ID` (Fish Audio fallback voiceover)
- Local models (inside WSL, **too large for GitHub**):
  - Qwen3-TTS (`/root/models/qwen3tts`, cloned voice)
  - faster-whisper-large-v3 (subtitle transcription)
- Fonts (**131MB excluded**): open-source CJK fonts under
  `skills/杜蕾斯文案skill/assets/fonts/cjk/` (Noto Sans/Serif SC, LXGW WenKai, ZCOOL…).
  On this machine the global skill dir already has them — running
  `python checks/sync_skills.py --apply` restores them from global. On a new machine,
  download from their official sources (Noto, LXGW, ZCOOL).

## Image generation note (when Agnes is flaky)

- Sample/board prompts live in `docs/style-assets/` (sample-prompts.md / style-board-prompts.md).
- **Do not retry when Agnes output is bad**: hand these prompts to the user and let them
  generate on their own platform (e.g. runninghub); the AI handles review/rating/renaming
  afterwards (LESSONS Q1).
- The 42 style assets are in `voxvideo/ref/style-assets/` (21 samples + 21 six-grid
  style boards + style-grid).

## Quick index

```
checks/                 Programmatic check layer (run_all; 167 tests against false-passes)
docs/
  second-step-brief.md  Step-2 brief (10 matching constraints)
  style-mapping.md      21 directions ↔ 6 existing styles
  check-mapping.md      srt-vox 16 items ↔ our checkers
  review-checklist.md   Reference-image 8-dim + video 6-dim
  style-assets/         Sample/board prompts + rating table
scripts/                Generation/review/grid/merge scripts
skills/                 Skill snapshots (whitelist)
vendor/srtvox-director/ Upstream reference snapshot (not redistributed)
voxvideo/               VOX package program (24 style registrations + 42 assets + 104 tests)
NEXTSESSION.md          Session handoff (read first in a new session)
PROGRESS.md             Progress ledger
DECISIONS.md            Decision records
关卡定义.md              Gate definitions (Chinese)
```

## License

Private repository — not open source, not publicly redistributed (DECISIONS 2026-08-17).
Upstream srt-vox-director has no LICENSE; this project only adopts its methodology
(structure adopted, expression rewritten) and all 21 style assets are self-made —
see `vendor/srtvox-director/VENDOR-NOTICE.md`.
