# Current State

_Last updated: 2026-11-15_

## Authorized project

**Standing authorization for Projects 04–50.** The owner (2026-11-12) asked for all remaining
projects to be built sequentially without waiting for a per-project command. Projects 01–07 are
closed; do not rewrite their history unless the owner names them. Continue automatically with the
first project that is not verified and published (currently **Project 08**).

## Programme status

| Item | Value |
|---|---|
| Phase | Building sequentially (standing authorization) |
| Current project | 07 complete; next is 08 |
| Projects completed | 7 / 50 |
| Projects published to GitHub | 7 / 50 |
| Workspace | `C:\Users\Swayam Naik\TOP-50-CLAUDE-PROJECTS` |
| GitHub repo | https://github.com/Swaraj52/top-50-claude-projects |
| Latest release | `project-07-v1.0` |

## Last project: 07, Email Command Center ("Switchboard")

- **Stack:** FastAPI + Jinja2 templates + HTMX (server-rendered, no JS build), SQLite + Alembic,
  Claude for optional summaries and reply drafts with a labelled deterministic local writer
- **Port:** 8007 (single process). Preview: `python PROJECT_07/backend/scripts/preview.py`,
  launch.json entry `project-07-switchboard`; demo `demo@switchboard.example` / `switchboard-demo`
- **Tests:** 201 backend tests, all passing
- **Verified:** registration/login/session/CSRF, pasted intake and `.eml` upload, `Message-ID`
  dedupe, threading by cleaned subject inside a mailbox with a closed-thread split, five routes
  with visible reasons, explainable priority score, local summaries and drafts in three tones,
  mark-sent semantics, follow-ups with natural-language dates and Overdue/Today/Next seven
  days/Later/No date grouping, inbox views plus search across subjects and bodies, mailbox filter,
  settings, VIP list, password change ending other sessions, JSON export, importer round trip
  (12 threads, 15 messages, 4 drafts, 7 follow-ups; second and third imports skipped all 12),
  account deletion, light/dark, 390 px mobile with no horizontal scroll; 12 screenshots captured
  from the live app
- **Not verified live:** the Claude summary and draft paths (no API key); the local writer is what
  the screenshots show and the UI labels it `Local`
- **Deliberate omission:** no IMAP, OAuth or SMTP. Mail arrives by paste, `.eml` upload or a local
  JSON import; "mark sent" records locally only
- **Owner's data:** requested after release, per `PROJECT_07/docs/YOUR_DATA.md`
- **Known errors:** none

## Standing constraints

- Free-only tooling and models. Application AI stays optional via the user's own key.
- No secrets committed, no force-push, no destructive actions against unrelated work.
- Every project: real persistence, working UI, tests, README/PRD/architecture/YOUR_DATA,
  screenshots, a tag and a push; then continue.
