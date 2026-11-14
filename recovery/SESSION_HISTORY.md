# Session History

## Session 1: 2026-11-07 (setup)

- **Project worked on:** none (programme setup only, per the owner's instruction).
- **Done:** extracted and checked all 50 projects from the PDF. Created the workspace, root
  docs, `projects.json`, the doc generator, 50 project folders, the recovery system and
  `CLAUDE.md`. Initialized Git on `main` and committed the setup. Checked the toolchain and
  GitHub (CLI missing).
- **Setup commit:** `cc83b6d` chore(repo): set up Top 50 Claude Projects workspace.
- **GitHub:** the owner confirmed account Swaraj52, kept the global Git identity, installed `gh`
  and approved the device login. Created the public `Swaraj52/top-50-claude-projects`, pushed
  `main` and checked that the remote matches local.
- **Remaining:** every project is pending, waiting for `Start Project 1`.

## Session 1 (continued): 2026-11-07, Project 01

- **Authorized by:** the owner's command `Start Project 1`.
- **Built:** Daybook. FastAPI/SQLite backend (auth, tasks, reminders, events, ICS calendars,
  IMAP email, priorities, dashboard, Claude/rule briefing) and a React frontend (Today, Tasks,
  Calendar, Inbox, Settings, Ctrl+K quick add, reminder notifications, light/dark, mobile).
- **Verified:** 74 backend and 30 frontend tests; manual browser run of all core flows; a real
  public ICS feed. Four UI bugs were found in the browser run, fixed and covered by tests.
- **Commits:** `76642d6` docs, `1c88e61` backend, `6dbb078` frontend, `8a2f79c` E2E fixes,
  `2355900` release + tag `project-01-v1.0`. Pushed and verified on GitHub (remote = local,
  tag present, 93/93 files).
- **Not verified live:** the Claude briefing (no key) and IMAP (no mailbox credentials).
- **Recovery instructions:** authorized project is NONE. Wait for `Start Project 2`.
- **Follow-up (owner request "provide preview of each project"):** added
  `PROJECT_01/backend/scripts/preview.py` (fresh demo data + built UI on :8001), a
  `.claude/launch.json` entry `project-01-daybook`, and a live-preview step in the definition of
  done (`MASTER_README.md`, `CLAUDE.md`, `ARCHITECTURE_OVERVIEW.md`). Opened the preview for the
  owner in the Browser pane. Released as tag `project-01-v1.1`.
- **Recovery instructions:** read `CURRENT_STATE.md`. Authorized project is NONE, so wait for
  `Start Project N`.

## Sessions 2–3: 2026-11-08 to 2026-11-09, Project 02

- **Authorized by:** the owner's command `Start Project 2`. The owner paused ("stop this for now") and
  resumed ("continue"). The work resumed from the uncommitted backend after re-checking the code.
- **Built:** Stacks. FastAPI + SQLite FTS5 backend (SSRF-safe capture of articles, YouTube,
  newsletters, PDFs; inbox/library/tags; BM25 search; summaries; Ask Your Library with cited
  answers) and a React card-catalogue frontend.
- **Verified:** 60 backend + 12 frontend tests; live browser run capturing a real Wikipedia article
  and a real YouTube transcript; search and Ask over real content; light, dark and mobile. Three issues
  were found in that run and fixed (User-Agent policy, carried-over tags, duplicate label).
- **Commits:** `ac36f49` docs, `132a929` backend, `cc8dd4e` frontend, `f44155d` fixes, seed, preview and
  screenshots, `f9e3c67` release + tag `project-02-v1.0`. Pushed and verified on GitHub (remote =
  local, tag present, 86/86 files).
- **Not verified live:** Claude summaries and answers (no API key).
- **Recovery instructions:** authorized project is NONE. Wait for `Start Project 3`.

## Session 4: 2026-11-09, credit and data rule, then Project 03

- **Owner requests:** "put my name in all projects Swayam and take the data for each project
  required from me after the projects are completed", then "start with project 3".
- **Credit change:** Swayam credited in Projects 01 and 02 (README author line, in-app credit, API
  contact metadata, demo display name) and the rule added to `CLAUDE.md` and `MASTER_README.md`
  (`91f2020`, tags `project-01-v1.2`, `project-02-v1.1`).
- **Built:** Shutdown. A server-rendered FastAPI + Jinja2 + HTMX app: Today (tasks, work log,
  blockers, check-in), end-of-day review (Claude or rules), triage of unfinished work, a capacity-aware
  tomorrow plan, weekly trends with SVG charts, history and settings. Demo seed simulated day by day
  with the real planner and reviewer; one-command preview; JSON data import.
- **Verified:** 33 backend tests; browser run of the full triage, generate and commit flow, with the
  database checked afterwards; trends, history, settings, both themes and mobile. Five issues found
  in that run were fixed (in-progress order, weekend streak, "0 day(s)" wording, mobile nav, "later"
  without JavaScript).
- **Commits:** `8cb8fd7` docs, `460bbab` app, `0a3c2e8` seed, preview and import, `2bac5a1` release +
  tag `project-03-v1.0`. Pushed and verified on GitHub (remote `main` = local, tag present, 69/69
  `PROJECT_03/` files).
- **Not verified live:** the Claude-written review (no API key).
- **Recovery instructions:** authorized project is NONE. Wait for `Start Project N`. The Project 01/02
  follow-ups in `NEXT_ACTIONS.md` need the owner's go-ahead.

## Session 5: 2026-11-12, Project 04 (standing authorization)

- **Authorized by:** the owner's new instruction to build Projects 04–50 sequentially, recorded in
  `CLAUDE.md` and `CURRENT_STATE.md`.
- **Built:** Summit. A server-rendered FastAPI + Jinja2 + HTMX goal tracker: weighted milestones,
  straight-line pace and at-risk signals, a weekly plan with carry-over, confidence check-ins and
  streaks, an optional Claude coach with a labelled deterministic planner, eight-week insights,
  a printable goal review, JSON export/import and account deletion. Demo seed has eight weeks of
  actions and check-ins; one-command preview on :8004.
- **Verified:** 41 backend tests; browser run of every page at desktop, mobile, light and dark;
  the screenshot pass found and fixed three real UI bugs (HTML `.bar` colliding with SVG bars,
  stretched SVG chart text, invisible sidebar sign-out). Export → import round trip checked against
  a scratch database (4 goals, 15 milestones, 41 actions, 54 check-ins).
- **Commits:** `c4583ed` standing authorization, `9d7b0b8` backend + UI, `813eb45` preview/seed/import,
  `4acb1ee` docs and screenshots, `425e717` release + tag `project-04-v1.0`.
- **Not verified live:** the Claude coach (no API key); the local planner is what the screenshots
  show and the UI labels it as such.
- **Recovery instructions:** continue with Project 05 (Habit & Routine Coach) without waiting.

## Session 6: 2026-11-13, Project 05 (standing authorization)

- **Authorized by:** the standing instruction to build Projects 04–50 sequentially, reconfirmed by
  the owner's `/continue`.
- **Built:** Cadence. A server-rendered FastAPI + Jinja2 + HTMX habit coach: per-user habits with
  schedules and cues, daily done/rest logs, pending-today semantics, streaks, week grid and report,
  weekly reflections, eight-week insights, optional Claude coach with a labelled local fallback,
  JSON export/import and account deletion. One-command preview on :8005 with an eight-week seed.
- **Verified:** 76 backend tests. Browser and screenshot pass at desktop, mobile, light and dark
  found and fixed three real issues: paused habits dragging down reports, today counted as missed,
  and a clipped mobile nav; the week grid also gained a sticky habit column and a swipe hint.
- **Commits:** `86d704b` app, `04ba203` tests/tooling, `bfe2630` docs and screenshots, `481e54f`
  release + tag `project-05-v1.0`.
- **Not verified live:** the Claude coach (no API key); the UI shows locally generated notes.
- **Recovery instructions:** continue with Project 06 without waiting. Read `CURRENT_STATE.md`.

## Session 7: 2026-11-14, Project 06 (standing authorization, resumed after restart)

- **Authorized by:** the standing instruction to build Projects 04–50 sequentially, continued with the
  owner's `/continue`.
- **Built:** Quorum. A server-rendered FastAPI + Jinja2 + HTMX meeting memory: paste notes, get a
  summary, a decision log and follow-ups with owners and due dates, then search the whole archive.
  A deterministic local extractor is the default; Claude is optional, validated and labelled.
  Includes Agreed/Revisit decisions, timezone-aware follow-up groups, JSON export/import, account
  deletion and a one-command preview on :8006 with a six-meeting seed built by the real extractor.
- **Verified:** 144 backend tests across 7 files; browser pass at desktop, phone, light and dark;
  13 Playwright screenshots. Export → import round trip against a scratch database wrote 6 meetings,
  13 decisions and 17 actions, and a second run skipped all 6 meetings.
- **Fixed in the pass:** a truncated "Follow up with…" action title (over-eager prefix), an
  unassigned owner pill colliding with the `.empty` page style, a missing `Due` label, a duplicated
  month in the archive date block, lowercase action status, a wrapped memory search button, and a
  clipped phone nav (now a 3×2 grid; measured `scrollWidth == innerWidth == 390`).
- **Encoding repair:** PowerShell `Set-Content` had double-encoded punctuation in three files and
  added BOMs to five Python files; all repaired with Python and re-scanned clean.
- **Commits:** `357ec06` app, `200fcf7` tests/tooling, `6833a90` docs and screenshots, `8c2f569`
  release + tag `project-06-v1.0`.
- **Not verified live:** Claude extraction (no API key); the local extractor is what the screenshots
  show and the UI labels it `Local`.
- **Recovery instructions:** continue with Project 07 (Email Command Center, port 8007) without
  waiting. Read `CURRENT_STATE.md` and `NEXT_ACTIONS.md`.


