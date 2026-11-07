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

### B-002: GitHub account and commit identity to confirm

- **Impact:** commits could be attributed to the wrong account, or expose a personal email
  address once the repo is public.
- **Found:** the programme expects GitHub user `Swaraj52`, but the global Git identity on this
  machine is `Swarajya1630`, with a personal Gmail address. Both accounts exist on GitHub.
  `top-50-claude-projects` does not publicly exist under either account. A private repo with
  that name would also return 404, so `gh` must confirm this after sign-in.
- **Needs:** the owner confirms the target account, and whether to set a repo-local commit
  email (for example the account's `users.noreply.github.com` address) before the first push.
  Unpushed setup commits can be re-authored safely at that point.

## Resolved

_None yet._
