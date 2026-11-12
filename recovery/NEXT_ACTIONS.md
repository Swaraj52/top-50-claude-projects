# Next Actions

_Last updated: 2026-11-12_

## Continue now

1. **Project 05: Habit & Routine Coach.** Category 1, port 8005. Features from the PDF: habit
   calendar, streaks, reflection prompts, weekly report. Use the established FastAPI + Jinja2 +
   HTMX + SQLite stack, a fresh design, real tests, docs, screenshots and a tag. Then continue to
   Project 06 without waiting.
2. Reuse the shared tooling: `shared-resources/.venv` (project `.venv` is a junction), the headless
   Playwright screenshot pattern, and `render_docs.py` after each release.

## Owner input (collect after completion, do not block the build)

1. **Owner's data for Projects 01–04.** Each project's `docs/YOUR_DATA.md` says what is safe to
   share and how its `scripts/import_data.py` loads it. Secrets go only into the app's forms or the
   project `.env`.
2. *(Optional)* Live Claude verification for Projects 01–04 needs the owner's own
   `ANTHROPIC_API_KEY` and approval of the small per-call spend.

## Pending follow-ups for Projects 01 and 02 (owner request, 2026-11-09)

1. Retake the screenshots that show the demo user's name or the credit (P01: most pages; P02:
   inbox, mobile, sign-in) so they show "Swayam".
2. Add `docs/YOUR_DATA.md` and `scripts/import_data.py` to Projects 01 and 02. These need an
   explicit owner request that names them, per the standing rule about closed projects.

## Useful commands

```bash
python shared-resources/scripts/render_docs.py --check
gh auth status
cd PROJECT_04/backend && .venv/Scripts/python.exe -m pytest   # 41 passed
cd PROJECT_04/backend && .venv/Scripts/python.exe scripts/preview.py  # :8004
```

## Tooling notes

- `preview_start` with the launch.json name opens a preview in the Browser pane. The built-in
  screenshot tool needs a visible tab; headless Playwright works without one and is already
  installed in `shared-resources/.venv` (`playwright install chromium`).
- Take screenshots at 1440 px, 390 px and with `color_scheme="dark"`; wait for `networkidle` and a
  short settle before capturing.
- `data/*.db`, `.venv/` and browser artefacts are git-ignored; never commit them.
