# Next Actions

_Last updated: 2026-11-07_

## Waiting on the owner

1. **Command to start Project 02** (Second Brain / Life Library). Nothing starts until the owner
   says `Start Project 2`.
2. *(Optional, Project 01)* To verify the Claude briefing live, the owner adds their own
   `ANTHROPIC_API_KEY` to `PROJECT_01/.env` and approves the (small) API spend. To verify IMAP,
   the owner connects their own mailbox in Settings. Neither is required for completion.

## When `Start Project 2` is received

1. Set **Authorized project** in `CURRENT_STATE.md` to `02, Second Brain / Life Library`.
2. Follow the per-project checklist in `MASTER_README.md` §3.
3. Reuse lessons from Project 01 (`DEVELOPMENT_LOG.md`): Playwright MCP can only write inside
   `C:\Users\Swayam Naik\OneDrive\Documents\Sentivision`. Save screenshots to
   `.playwright-mcp/shots/` there, move them into the project, then delete that folder.

## Useful commands

```bash
python shared-resources/scripts/render_docs.py --check   # docs in sync with projects.json?
gh auth status                                          # should report Swaraj52
cd PROJECT_01/backend && .venv/Scripts/python -m pytest  # 74 passed
cd PROJECT_01/frontend && npm test                       # 30 passed
```
