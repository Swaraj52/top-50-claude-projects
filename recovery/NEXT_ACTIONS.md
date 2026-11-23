# Next Actions

_Last updated: 2026-11-23_

## Continue now

1. **Project 10, Business Operations Hub.** Build it in `PROJECT_10/` with the established
   FastAPI + Jinja2 + HTMX + SQLite stack unless the project clearly needs a different one. The
   brief: centralise recurring business processes, SOPs and team responsibilities, with an SOP
   library, process checklists and an ownership tracker. Fresh visual design, real persistence,
   tests, docs, screenshots, a tag and a push. Do not wait for a command.
2. Reuse the shared tooling: `shared-resources/.venv` (project `.venv` is a junction), the headless
   Playwright screenshot pattern, and `render_docs.py` after each release. Project 10 preview runs
   on **port 8010**.

## Owner input (collect after completion, do not block the build)

1. **Owner's data for Projects 01–09.** Each project's `docs/YOUR_DATA.md` says what is safe to
   share and how its `scripts/import_data.py` loads it. Secrets go only into the app's forms or the
   project `.env`.
2. *(Optional)* Live Claude verification for Projects 01–09 needs the owner's own
   `ANTHROPIC_API_KEY` and approval of the small per-call spend.
3. **Mail access is a secret.** Project 07 deliberately has no mailbox connection: it works from
   pasted or imported mail, and never asks for a password or app password. Do not add one later
   without an explicit owner request.

## Pending follow-ups for Projects 01 and 02 (owner request, 2026-11-09)

1. Retake the screenshots that show the demo user's name or the credit (P01: most pages; P02:
   inbox, mobile, sign-in) so they show "Swayam".
2. Add `docs/YOUR_DATA.md` and `scripts/import_data.py` to Projects 01 and 02. These need an
   explicit owner request that names them, per the standing rule about closed projects.

## Useful commands

```bash
python shared-resources/scripts/render_docs.py --check
gh auth status
cd PROJECT_09/backend && .venv/Scripts/python.exe -m pytest   # 332 passed
cd PROJECT_09/backend && .venv/Scripts/python.exe scripts/preview.py  # :8009
```

## Tooling notes

- `preview_start` with the launch.json name opens a preview in the Browser pane. The built-in
  screenshot tool needs a visible tab; headless Playwright works without one and is already
  installed in `shared-resources/.venv` (`playwright install chromium`).
- Take screenshots at 1440 px, 390 px and with `color_scheme="dark"`; wait for `networkidle` and a
  short settle before capturing, and re-capture after any CSS change (the `?v=` query busts cache).
- On a phone, verify `document.documentElement.scrollWidth === window.innerWidth`; Project 09's
  rail becomes a wrapped top bar under 900 px and the portfolio measured 390 px.
- Never edit non-ASCII files with PowerShell `Get-Content`/`Set-Content`; it double-encodes `·`,
  `–` and `…`. Use the editor, or Python with `encoding="utf-8", newline="\n"`.
- `data/*.db`, `.env` and browser artefacts are git-ignored; never commit them.
