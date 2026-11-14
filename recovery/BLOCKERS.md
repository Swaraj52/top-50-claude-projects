# Blockers

_Last updated: 2026-11-14_

## Open

_None._

## Resolved

### B-005: PowerShell text replacement corrupted UTF-8 templates (resolved 2026-11-14)

- `Get-Content`/`Set-Content -Encoding utf8` double-encoded `·`, `×` and `…` into sequences such as
  `Â·` and `â€¦` across `actions.html`, `meeting_detail.html` and `app.css`, and added BOMs to five
  Python files.
- Repaired with Python (`encoding="utf-8-sig"` in, `encoding="utf-8", newline="\n"` out), then
  scanned every Project 06 text file for BOMs and double-encoded sequences: zero remaining.
- Rule added to `NEXT_ACTIONS.md`: never edit non-ASCII files with PowerShell text cmdlets.

### B-004: Report logic treated open and paused habits as failures (resolved 2026-11-13)

- Screenshot review showed today's unlogged habits counted as missed, and a paused habit lowering
  the Week/Insights completion rate.
- Fixed in `habitmath.py` (`pending` today, decided-day rates), filtered paused habits from the
  Week/Reflect/Insights queries, added dashed pending states, and covered both rules with tests.
  The week now shows 16/16 decided days with today still open.

### B-003: Built-in browser screenshots need a visible tab (resolved 2026-11-12)

- `browser.screenshot` failed with "Screenshot needs a visible tab" in the headless session.
- Installed Playwright + Chromium into `shared-resources/.venv` (free) and captured screenshots
  headlessly with an explicit login flow. This is now the standard screenshot path.

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
