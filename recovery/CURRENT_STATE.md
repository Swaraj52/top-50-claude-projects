# Current State

_Last updated: 2026-11-16_

## Authorized project

**Standing authorization for Projects 04–50.** The owner (2026-11-12) asked for all remaining
projects to be built sequentially without waiting for a per-project command. Projects 01–08 are
closed; do not rewrite their history unless the owner names them. Continue automatically with the
first project that is not verified and published (currently **Project 09**).

## Programme status

| Item | Value |
|---|---|
| Phase | Building sequentially (standing authorization) |
| Current project | 08 complete; next is 09 |
| Projects completed | 8 / 50 |
| Projects published to GitHub | 8 / 50 |
| Workspace | `C:\Users\Swayam Naik\TOP-50-CLAUDE-PROJECTS` |
| GitHub repo | https://github.com/Swaraj52/top-50-claude-projects |
| Latest release | `project-08-v1.0` |

## Last project: 08, Personal Knowledge Search ("Loom")

- **Stack:** FastAPI + Jinja2 templates + HTMX (server-rendered, no JS build), SQLite + Alembic,
  Claude for an optional answer rewrite with a labelled deterministic extractive answer underneath
- **Port:** 8008 (single process). Preview: `python PROJECT_08/backend/scripts/preview.py`,
  launch.json entry `project-08-loom`; demo `demo@loom.example` / `loom-demo`
- **Tests:** 181 backend tests, all passing
- **Verified:** registration/login/session/CSRF, item CRUD for four kinds (note, article,
  reference, snippet), collections and tags, markdown/text/HTML upload (512 KB cap, HTML stripped
  to text), lexical BM25-style search with visible query understanding, synonym expansion, quoted
  phrases, `kind:`/`tag:`/`in:`/`is:starred` filters, highlighted snippets, tag-first topic
  clusters with a generic-term blacklist and overlap, extractive Ask with citations, settings,
  password change ending other sessions, JSON export, importer round trip (14 items and 4
  collections matched; a second run skipped all 14), account deletion, light/dark, 390 px mobile
  with no horizontal scroll; 12 screenshots captured from the live app
- **Not verified live:** the Claude answer rewrite (no API key); the local extractive answer is what
  the screenshots show and the UI labels it `Local`
- **Deliberate omission:** no crawler, page fetching or embeddings. Search is lexical and explains
  itself; items arrive by typing, upload or JSON import
- **Owner's data:** requested after release, per `PROJECT_08/docs/YOUR_DATA.md`
- **Known errors:** none

## Standing constraints

- Free-only tooling and models. Application AI stays optional via the user's own key.
- No secrets committed, no force-push, no destructive actions against unrelated work.
- Every project: real persistence, working UI, tests, README/PRD/architecture/YOUR_DATA,
  screenshots, a tag and a push; then continue.
