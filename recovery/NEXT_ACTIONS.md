# Next Actions

_Last updated: 2026-11-07_

## Waiting on the owner

1. **Command to start Project 01.** Nothing starts until the owner says `Start Project 1`.
2. **GitHub access** (B-001). The owner installs the GitHub CLI and signs in, then the developer verifies:
   ```bash
   winget install --id GitHub.cli -e
   gh auth login
   gh auth status
   ```

## Once GitHub access is verified

1. `gh auth status`: the signed-in login must be `Swaraj52`. Then run `gh auth setup-git`.
2. `gh repo view Swaraj52/top-50-claude-projects` must fail with "not found". Never overwrite an existing repo.
3. `gh repo create Swaraj52/top-50-claude-projects --public --source . --remote origin --description "50 independently runnable applications built from the Top 50 Claude Project Ideas list"`
4. Scan for secrets, then `git push -u origin main`.
5. Check the files on GitHub, then update `COMPLETED_FEATURES.md`, `BLOCKERS.md` and `CURRENT_STATE.md`.

## When `Start Project 1` is received

1. Set **Authorized project** in `CURRENT_STATE.md` to `01 – Personal Dashboard`.
2. Follow the per-project checklist in `MASTER_README.md` §3.
