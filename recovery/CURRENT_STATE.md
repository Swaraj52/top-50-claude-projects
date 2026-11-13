# Current State

_Last updated: 2026-11-13_

## Authorized project

**Standing authorization for Projects 04–50.** The owner (2026-11-12) asked for all remaining
projects to be built sequentially without waiting for a per-project command. Projects 01–05 are
closed; do not rewrite their history unless the owner names them. Continue automatically with the
first project that is not verified and published (currently **Project 06**).

## Programme status

| Item | Value |
|---|---|
| Phase | Building sequentially (standing authorization) |
| Current project | 05 complete; next is 06 |
| Projects completed | 5 / 50 |
| Projects published to GitHub | 5 / 50 |
| Workspace | `C:\Users\Swayam Naik\TOP-50-CLAUDE-PROJECTS` |
| GitHub repo | https://github.com/Swaraj52/top-50-claude-projects |
| Latest release | `project-05-v1.0` on `481e54f` |

## Last project: 05, Habit & Routine Coach ("Cadence")

- **Stack:** FastAPI + Jinja2 templates + HTMX (server-rendered, no JS build), SQLite + Alembic,
  Claude for optional habit suggestions with a labelled deterministic fallback
- **Port:** 8005 (single process). Preview: `python PROJECT_05/backend/scripts/preview.py`,
  launch.json entry `project-05-cadence`; demo `demo@cadence.example` / `cadence-demo`
- **Tests:** 76 backend tests passing
- **Verified:** registration/login/session/CSRF, habit CRUD and status, day logging, pending-today
  and planned-rest semantics, paused-habit exclusion from Week/Reflect/Insights, streak and rate
  maths, week grid and report, weekly reflection upsert and streak, eight-week insights, coach
  fallback and rate limit, settings/export/delete, light/dark, 390 px mobile and a scrollable week
  grid; 12 screenshots captured from the live app
- **Not verified live:** the Claude-written suggestions (no API key); local coach shown instead
- **Owner's data:** requested after release, per `PROJECT_05/docs/YOUR_DATA.md`
- **Known errors:** none

## Standing constraints

- Free-only tooling and models. Application AI stays optional via the user's own key.
- No secrets committed, no force-push, no destructive actions against unrelated work.
- Every project: real persistence, working UI, tests, README/PRD/architecture/YOUR_DATA,
  screenshots, a tag and a push; then continue.
