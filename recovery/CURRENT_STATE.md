# Current State

_Last updated: 2026-11-23_

## Authorized project

**Standing authorization for Projects 04–50.** The owner (2026-11-12) asked for all remaining
projects to be built sequentially without waiting for a per-project command. Projects 01–09 are
closed; do not rewrite their history unless the owner names them. Continue automatically with the
first project that is not verified and published (currently **Project 10**).

## Programme status

| Item | Value |
|---|---|
| Phase | Building sequentially (standing authorization) |
| Current project | 09 complete; next is 10 |
| Projects completed | 9 / 50 |
| Projects published to GitHub | 9 / 50 |
| Workspace | `C:\Users\Swayam Naik\TOP-50-CLAUDE-PROJECTS` |
| GitHub repo | https://github.com/Swaraj52/top-50-claude-projects |
| Latest release | `project-09-v1.0` |

## Last project: 09, Business Strategy Planner ("Keystone")

- **Stack:** FastAPI + Jinja2 templates + HTMX (server-rendered, no JS build), SQLite + Alembic,
  Claude for an optional strategy-memo rewrite with a labelled deterministic local memo underneath
- **Port:** 8009 (single process). Preview: `python PROJECT_09/backend/scripts/preview.py`,
  launch.json entry `project-09-keystone`; demo `demo@keystone.example` / `keystone-demo`
- **Tests:** 332 backend tests, all passing
- **Verified:** registration/login/session/CSRF, venture CRUD and archive, nine-block canvas with
  completeness and gap prompts, impact-weighted SWOT with a ±3 balance band and top risks, revenue
  streams and costs with confidence weighting and 0.7/1.0/1.4 volume scenarios, now/next/later
  milestones with derived overdue and status transitions, KPIs with baseline-to-target progress,
  elapsed-time pace and SVG sparklines, a grounded one-page brief with save/reset and an optional
  Claude rewrite, settings, password change ending other sessions, JSON export, importer round trip,
  account deletion, light/dark, 390 px mobile with no horizontal scroll; 12 screenshots captured
  from the live app
- **Demo facts:** Sahaj base MRR ₹77,960, costs ₹25,900, margin ₹52,060 (67%), ARR ₹935,520,
  weighted MRR ₹72,560, break-even 15 units; two KPIs behind, one ahead; one milestone four days
  overdue; a second thin venture makes every empty state reachable
- **Not verified live:** the Claude memo rewrite (no API key); the local memo is what the screenshots
  show and the UI labels it `Local`
- **Deliberate omission:** no market feed, competitor crawler, currency conversion or cash-flow
  model. Every figure is typed in or arithmetic over typed values
- **Owner's data:** requested after release, per `PROJECT_09/docs/YOUR_DATA.md`
- **Known errors:** none

## Standing constraints

- Free-only tooling and models. Application AI stays optional via the user's own key.
- No secrets committed, no force-push, no destructive actions against unrelated work.
- Every project: real persistence, working UI, tests, README/PRD/architecture/YOUR_DATA,
  screenshots, a tag and a push; then continue.
