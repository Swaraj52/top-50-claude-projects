# Next Actions

_Last updated: 2026-11-09_

## Waiting on the owner

1. **Command to start the next project.** Nothing starts until the owner says `Start Project 4`
   (Personal Goal Tracker) or names another project.
2. **The owner's data for Projects 01–03.** Asked for after Project 03's release. Non-secret data
   given in chat is loaded with each project's import script; secrets go only into the app's forms
   or the project `.env`.
3. **Go-ahead for the Project 01/02 follow-ups** below.
4. *(Optional)* Verifying Claude features live in Projects 01–03 needs the owner's own
   `ANTHROPIC_API_KEY` in each project's `.env` and approval of the (small) spend.

## When `Start Project N` is received

1. Set **Authorized project** in `CURRENT_STATE.md`.
2. Follow `MASTER_README.md` §3, including the live preview (preview script + `launch.json`), the
   Swayam credit, `docs/YOUR_DATA.md` with an import script, and asking for the data at the end.
3. Tooling notes:
   - `preview_start` with the launch.json name opens a preview in the Browser pane.
   - Playwright screenshots can be saved straight to `PROJECT_NN/docs/screenshots/`.
     `.playwright-mcp/` is git-ignored; delete it after a run.
   - Take screenshots with `reducedMotion: reduce` to avoid half-animated frames.

## Useful commands

```bash
python shared-resources/scripts/render_docs.py --check
gh auth status
cd PROJECT_02/backend && .venv/Scripts/python -m pytest   # 60 passed
cd PROJECT_02/frontend && npm test                        # 12 passed
cd PROJECT_03/backend && .venv/Scripts/python -m pytest   # 33 passed
```

## Pending follow-ups for Projects 01 and 02 (owner request, 2026-11-09)

The "credit Swayam" change is done and pushed (READMEs, in-app credit, API metadata, demo name).
Still to do (Project 03 is finished; ask the owner before starting):
1. Retake the screenshots that show the demo user's name or the credit
   (P01: most pages; P02: inbox, mobile, sign-in) so they show "Swayam".
2. Add `docs/YOUR_DATA.md` and `scripts/import_data.py` to Projects 01 and 02. The importer
   creates a temporary session for the owner's account and calls the app's own API, so no password
   is needed. Then ask the owner for each project's data.
