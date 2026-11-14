# Current State

_Last updated: 2026-11-14_

## Authorized project

**Standing authorization for Projects 04–50.** The owner (2026-11-12) asked for all remaining
projects to be built sequentially without waiting for a per-project command. Projects 01–06 are
closed; do not rewrite their history unless the owner names them. Continue automatically with the
first project that is not verified and published (currently **Project 07**).

## Programme status

| Item | Value |
|---|---|
| Phase | Building sequentially (standing authorization) |
| Current project | 06 complete; next is 07 |
| Projects completed | 6 / 50 |
| Projects published to GitHub | 6 / 50 |
| Workspace | `C:\Users\Swayam Naik\TOP-50-CLAUDE-PROJECTS` |
| GitHub repo | https://github.com/Swaraj52/top-50-claude-projects |
| Latest release | `project-06-v1.0` on `8c2f569` |

## Last project: 06, Meeting Memory Assistant ("Quorum")

- **Stack:** FastAPI + Jinja2 templates + HTMX (server-rendered, no JS build), SQLite + Alembic,
  Claude for optional extraction with a labelled deterministic local fallback
- **Port:** 8006 (single process). Preview: `python PROJECT_06/backend/scripts/preview.py`,
  launch.json entry `project-06-quorum`; demo `demo@quorum.example` / `quorum-demo`
- **Tests:** 144 backend tests, all passing
- **Verified:** registration/login/session/CSRF, meeting capture, local extraction of summary,
  decisions, owners and due dates, decision log and Agreed/Revisit status, follow-up completion,
  edit and delete, timezone-aware Overdue/Today/This week/Later/No date grouping, owner filter,
  memory search across meetings, decisions and follow-ups, profile/timezone, password change,
  JSON export, account deletion, light/dark, 390 px mobile with a 3×2 nav grid; 13 screenshots
  captured from the live app
- **Not verified live:** the Claude extraction path (no API key); the local extractor is what the
  screenshots show and the UI labels it `Local`
- **Owner's data:** requested after release, per `PROJECT_06/docs/YOUR_DATA.md`
- **Known errors:** none

## Standing constraints

- Free-only tooling and models. Application AI stays optional via the user's own key.
- No secrets committed, no force-push, no destructive actions against unrelated work.
- Every project: real persistence, working UI, tests, README/PRD/architecture/YOUR_DATA,
  screenshots, a tag and a push; then continue.
