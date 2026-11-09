# Blockers

_Last updated: 2026-11-09_

## Open

_None._

## Resolved

### B-001: GitHub CLI not installed or authenticated (resolved 2026-11-07)

- The owner installed GitHub CLI 2.103.3 (`C:\Program Files\GitHub CLI\gh.exe`) and approved a
  browser device login. `gh auth status` reports **Swaraj52** with scopes
  `repo, workflow, read:org, gist`.
- `gh auth setup-git` was run, so git pushes to github.com authenticate through gh as Swaraj52.
- **Note:** shells opened before the install don't have `gh` on PATH. Open a new terminal, or
  call it by its full path.

### B-002: GitHub account and commit identity (resolved 2026-11-07)

- **Account:** the owner confirmed `Swaraj52`. The repo is `Swaraj52/top-50-claude-projects`.
- **Commit identity:** the owner chose to **keep the machine's global Git identity**
  (`Swarajya1630`). No repo-local identity is set and no commits are re-authored. Do not
  propose this change again unless the owner asks.
