# Current State

_Last updated: 2026-11-12_

## Authorized project

**Standing authorization for Projects 04–50.** The owner (2026-11-12) asked for all remaining
projects to be built sequentially without waiting for a per-project command. Projects 01–03 are
closed; do not rewrite their history unless the owner names them. Continue automatically with the
first project that is not verified and published (currently **Project 05**).

## Programme status

| Item | Value |
|---|---|
| Phase | Building sequentially (standing authorization) |
| Current project | 04 complete; next is 05, Habit & Routine Coach |
| Projects completed | 4 / 50 |
| Projects published to GitHub | 4 / 50 |
| Workspace | `C:\Users\Swayam Naik\TOP-50-CLAUDE-PROJECTS` |
| GitHub repo | https://github.com/Swaraj52/top-50-claude-projects |
| Latest release | `project-04-v1.0` on `425e717` |

## Last project: 04, Personal Goal Tracker ("Summit")

- **Stack:** FastAPI + Jinja2 templates + HTMX (server-rendered, no JS build), SQLite + Alembic,
  Claude for optional weekly plans with a labelled deterministic fallback
- **Port:** 8004 (single process). Preview: `python PROJECT_04/backend/scripts/preview.py`,
  launch.json entry `project-04-summit`; demo `demo@summit.example` / `summit-demo`
- **Tests:** 41 backend tests passing
- **Verified:** weighted milestone progress, pace states, dashboard, goal CRUD, weekly plan with
  carry-over, check-in upsert and streak, insights charts, goal review, settings/export/delete,
  import round trip, light/dark and 390 px mobile; screenshots captured from the live app
- **Not verified live:** the Claude-written plan (no API key); local planner shown instead
- **Owner's data:** requested after release, per `PROJECT_04/docs/YOUR_DATA.md`
- **Known errors:** none

## Standing constraints

- Free-only tooling and models. Application AI stays optional via the user's own key.
- No secrets committed, no force-push, no destructive actions against unrelated work.
- Every project: real persistence, working UI, tests, README/PRD/architecture/YOUR_DATA,
  screenshots, a tag and a push; then continue.
