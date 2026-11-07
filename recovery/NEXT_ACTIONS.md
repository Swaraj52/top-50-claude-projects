# Next Actions

_Last updated: 2026-11-07_

## Waiting on the owner

1. **Command to start Project 01.** Nothing starts until the owner says `Start Project 1`.

## When `Start Project 1` is received

1. Set **Authorized project** in `CURRENT_STATE.md` to `01 – Personal Dashboard`.
2. Follow the per-project checklist in `MASTER_README.md` §3.
3. Publish: after the release commit and tag, run `git push origin main --follow-tags`, then check
   that the remote `main` SHA matches the local one.

## Useful commands

```bash
python shared-resources/scripts/render_docs.py --check   # docs in sync with projects.json?
gh auth status                                          # should report Swaraj52
git log --oneline -5
```
