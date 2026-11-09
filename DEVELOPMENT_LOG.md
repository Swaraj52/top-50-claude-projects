# Development Log

Architectural decisions, dependency changes, bugs and their fixes. Newest entries go at the top
of each section.

## 2026-11-09: Project 03, Daily Review Agent ("Shutdown")

### Decisions

- **Server-rendered with HTMX** instead of another React SPA. A short end-of-day ritual is a series
  of forms, so Jinja2 pages work without JavaScript and HTMX swaps fragments in place. There's no
  Node toolchain, and the preview has no build step.
- **CSRF via a per-session synchronizer token** (hidden form field, plus `X-CSRF-Token` through
  `hx-headers`), and a double-submit cookie before sign-in. Both are checked with a constant-time compare.
- **The planner is deterministic and always runs.** Claude may only reorder existing candidate task ids,
  and the result is refilled to capacity, so an AI failure can never produce an invalid plan.
- **Carry counts are applied once per day** (`applied_carry_ids` in the review's plan), so regenerating
  or recommitting a review doesn't inflate them.
- **The review streak skips rest days** (days with no activity and no review), so weekends don't
  reset it.
- **Charts are inline SVG drawn on the server**, with `<title>` text and the same numbers in a
  collapsible data table, so there's no chart library.
- **Demo history is simulated day by day** with the real planner and reviewer, so History and Trends
  show the app's genuine output.

### Dependencies (PROJECT_03 only)

- FastAPI 0.162.2, SQLAlchemy 2.1.8, Alembic 1.20.1, Pydantic 2.14.3, pydantic-settings 2.16.2,
  Jinja2 3.1.6, python-multipart 0.0.33, anthropic 2.6.0, uvicorn 0.54.0, tzdata 2026.6.
- HTMX 2.0.11 vendored into `app/static/` with its licence (no CDN, so the CSP stays `script-src 'self'`).

### Bugs found and fixed

- **Commit stored the word "carry" as a date**, and carry counts could double on recommit. Found by
  reading the database after a browser run. Fixed and covered by the review test.
- **"Later" needed JavaScript.** The date now has its own `later_{id}` field.
- **The streak broke on weekends**; in-progress tasks were listed last; the review said "open for
  0 day(s)"; the phone navigation overflowed. All found in the browser run and fixed.
- `_auth_page` had a parameter named `name` that clashed with template values (`**values`). Renamed.

## 2026-11-08 to 11-09: Project 02, Second Brain / Life Library ("Stacks")

### Decisions

- **Search and retrieval on SQLite FTS5** (Porter stemmer, BM25) instead of embeddings. That means
  no extra API key or model download, and it's fast. Ask Your Library = BM25 passages, then a Claude
  answer grounded in them, with validated citations. Embeddings are listed as a future improvement.
- **FTS tables via raw SQL in Alembic**, excluded from autogenerate (`include_object`), and kept
  in sync by a service-layer indexer.
- **SSRF-safe fetching:** manual redirects with a public-IP check per hop. Content is stored and
  rendered as text only.
- **Honest User-Agent** with a contact URL (Wikimedia policy). Never pose as a browser.
- **Different visual identity** from Project 01 (card catalogue: Literata, Atkinson
  Hyperlegible, Courier Prime; sage and library green).

### Dependencies (PROJECT_02 only)

- Backend: same core as Project 01 (FastAPI 0.162.2, SQLAlchemy 2.1.8, Alembic 1.20.1, Pydantic
  2.14.3, anthropic 2.6.0…) plus trafilatura 2.3.1 (lxml 6.1.3), youtube-transcript-api 1.2.5 and
  pypdf 7.0.0. There's no cryptography dependency (no stored third-party secrets).
- Frontend: React 19.3, React Router 7, TanStack Query 5, Vite 8, TypeScript 7, Vitest 5;
  @fontsource Literata, Atkinson Hyperlegible and Courier Prime.

### Bugs found and fixed

- **Wikipedia 403** for the original User-Agent. It now uses a policy-compliant identity. Found in the live browser run.
- **Tags carried over** from one save to the next (the YouTube video was mis-tagged). They now clear
  after saving, with a Vitest assertion.
- **API tag order** differed between save and fetch. Tags are now always sorted.
- **Duplicate type label** on cards without a source. Plural duplicates removed from keyword tag suggestions.

## 2026-11-07: Project 01, Personal Dashboard ("Daybook")

### Decisions

- **Integrations without OAuth:** calendars via ICS feeds/files and email via read-only IMAP.
  These work with every provider and need no app registration. OAuth is listed as a future step.
- **Cookie sessions + CSRF header** instead of JWTs in localStorage. Only the token's SHA-256 is stored.
- **Briefing:** `claude-opus-5-5` (skill default) with structured JSON output, effort `low`,
  server-side refusal fallback, and Pydantic validation. The labelled rule engine is used without
  a key or on any failure. Tests use a fake client, so no credits are spent.
- **Timezones:** UTC in the database; "today" is computed in the profile timezone on both server
  and client (quick add parses dates in the profile zone, not the browser's).
- **Fonts self-hosted** via @fontsource (no Google Fonts request at runtime).

### Dependencies (PROJECT_01 only)

- Backend: fastapi 0.162.2, uvicorn 0.54.0, SQLAlchemy 2.1.8, alembic 1.20.1, pydantic 2.14.3,
  pydantic-settings 2.16.2, email-validator 2.3.0, python-multipart 0.0.33, httpx 0.28.1,
  icalendar 7.3.0, recurring-ical-events 3.8.2, cryptography 50.0.2, anthropic 2.6.0, tzdata
  2026.6; dev: pytest 9.2.0.
- Frontend: react/react-dom 19.3, react-router-dom 7.18, @tanstack/react-query 5.107,
  chrono-node 2.10, @fontsource fonts; dev: vite 8.3, @vitejs/plugin-react 6.2, typescript 7.0,
  vitest 5.1, jsdom 29, @testing-library/*.

### Bugs found and fixed

- **AI answers missing fields were accepted** (the length-trimming step filled in defaults).
  Required fields are now enforced before trimming (pytest).
- **Sign-in/out did not switch views:** `queryClient.clear()` orphaned the App's `me` observer.
  Now only non-session queries are removed. Regression tests were confirmed to fail on the old code.
- **Reminder toasts persisted** after the reminder was handled elsewhere. The watcher now drops them (Vitest).
- **Week view columns misaligned** because only the body scrolled. Header and body now share one
  scroll container. Short events render compactly.
- `daysBetween` used 1-based months as `Date.UTC` month indexes (wrong across month ends). Fixed
  before release and covered by tests.

### Tooling notes

- **Live previews (owner request):** each project gets a one-command preview with demo data and a
  `.claude/launch.json` entry. The Browser pane's `preview_start` reads `launch.json` from the
  folder the Claude session started in. If that isn't this workspace, start the preview in a
  terminal tab and open the URL with `preview_start` `url` instead.
- The Playwright MCP server may only write under
  `C:\Users\Swayam Naik\OneDrive\Documents\Sentivision` (its configured root). Screenshots are
  saved to `.playwright-mcp/shots/` there, moved into the project, and that folder is then deleted.

## 2026-11-07: Programme setup

### Decisions

- **Workspace location:** `C:\Users\Swayam Naik\TOP-50-CLAUDE-PROJECTS`, outside OneDrive so
  that `node_modules/` and virtualenvs are not synced, and outside any other Git repository.
- **Single repository:** all 50 projects in one repo, `Swaraj52/top-50-claude-projects`
  (account confirmed by the owner), to be public, with each project isolated in `PROJECT_NN/`.
- **User-controlled execution:** no project starts without the explicit command
  `Start Project N`. Work stops after each project. Recorded in `MASTER_README.md`,
  `CLAUDE.md` and `recovery/CURRENT_STATE.md`.
- **Source of truth:** `projects.json` holds project metadata and progress. The tracker, the
  index, the README tables and placeholder READMEs are generated by
  `shared-resources/scripts/render_docs.py` (stdlib only), so the 50 rows stay consistent across files.
- **Port scheme:** backend `8000+N`, frontend `5100+N`, so projects can run side by side.
- **Descriptions:** the source PDF's descriptions are in Hinglish. Each project keeps the
  original text plus an English version. Names, categories and core features are unchanged.

### Environment verified

- Python 3.13.7, Node.js 24.11.0, npm 11.6.1, Git 2.51.2 (Windows 11).
- GitHub CLI 2.103.3 installed by the owner and signed in as Swaraj52. `gh auth setup-git`
  configured. Public repo `Swaraj52/top-50-claude-projects` created and `main` pushed.

### Dependency changes

- None. No packages have been installed for any project.
