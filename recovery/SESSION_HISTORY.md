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
