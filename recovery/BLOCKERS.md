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

### B-002: commit identity for the public repo (account confirmed)

- **Account: confirmed `Swaraj52`** by the owner on 2026-11-07. The repo will be
  `Swaraj52/top-50-claude-projects`. It does not exist publicly. A private repo with that name
  would also return 404, so `gh` must confirm after sign-in.
- **Still open:** the global Git identity on this machine is `Swarajya1630`, with a personal
  Gmail address. Commits made with it would show that email publicly and would not link to
  `Swaraj52`.
- **Proposed fix (awaiting the owner's OK):** a repo-local identity
  `Swaraj52 <195276089+Swaraj52@users.noreply.github.com>` (GitHub's private noreply address
  for that account). Then re-author the unpushed setup commits before the first push.
- **Also check at push time:** Git Credential Manager may hold credentials for the other account.
  Run `gh auth setup-git` after `gh auth login` so pushes go out as `Swaraj52`.

## Resolved

_None yet._
