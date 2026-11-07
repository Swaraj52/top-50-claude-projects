# Blockers

_Last updated: 2026-11-07_

## Open

### B-001: GitHub CLI not installed or authenticated

- **Impact:** the public repo cannot be created or pushed to yet. Local development is not affected.
- **Found:** `gh` is not on PATH, and `C:\Program Files\GitHub CLI\gh.exe` does not exist. Git's
  credential helper is `manager`, but creating a repository needs the GitHub API.
- **Needs:** the owner runs `winget install --id GitHub.cli -e` and then `gh auth login` (browser
  sign-in). Credentials are never shared in chat.
- **Workaround:** all work is committed locally. Pushing is a one-step catch-up once auth works.

## Resolved

### B-002: GitHub account and commit identity (resolved 2026-11-07)

- **Account:** the owner confirmed `Swaraj52`, so the repo is `Swaraj52/top-50-claude-projects`.
  It does not exist publicly. A private repo with that name would also return 404, so `gh` must
  confirm after sign-in.
- **Commit identity:** the owner chose to **keep the machine's global Git identity**
  (`Swarajya1630`). No repo-local identity is set and no commits are re-authored. Do not
  propose this change again unless the owner asks.
- **Still check at push time:** Git Credential Manager may hold credentials for a different
  account. Run `gh auth setup-git` after `gh auth login` so pushes authenticate as `Swaraj52`.
