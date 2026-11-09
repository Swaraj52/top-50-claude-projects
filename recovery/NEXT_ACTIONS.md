# Next Actions

_Last updated: 2026-11-09_

## Waiting on the owner

1. **Command to start Project 03** (Daily Review Agent). Nothing starts until the owner says
   `Start Project 3`.
2. *(Optional)* Verifying Claude features live in Projects 01 and 02 needs the owner's own
   `ANTHROPIC_API_KEY` in each project's `.env` and approval of the (small) spend.

## When `Start Project 3` is received

1. Set **Authorized project** in `CURRENT_STATE.md` to `03, Daily Review Agent`.
2. Follow `MASTER_README.md` §3, including the live-preview step (preview script + `launch.json`).
3. Tooling notes:
   - This session now starts in the workspace, so `preview_start` with the launch.json name works.
   - Playwright screenshots can be saved straight to `PROJECT_NN/docs/screenshots/`.
     `.playwright-mcp/` is git-ignored.
   - Take screenshots with `reducedMotion: reduce` to avoid half-animated frames.

## Useful commands

```bash
python shared-resources/scripts/render_docs.py --check
gh auth status
cd PROJECT_02/backend && .venv/Scripts/python -m pytest   # 60 passed
cd PROJECT_02/frontend && npm test                        # 12 passed
```
