# Working rules for this repository

## Execution control (highest priority)

- **Standing authorization (owner, 2026-11-12):** build Projects 04–50 sequentially, without
  stopping for routine approval. This supersedes the earlier one-project-at-a-time rule.
- After a context reset or new session, recover state (below), report it, and continue from the
  first project that is not verified and published. Do not restart completed projects.
- Changes to completed Projects 01–03 need an explicit request that names them; do not rewrite
  their history while working on new projects.

The current authorization lives in `recovery/CURRENT_STATE.md` → **Authorized project**.

## On session start

1. Read `recovery/CURRENT_STATE.md`, `recovery/NEXT_ACTIONS.md` and `recovery/BLOCKERS.md`.
2. Run `git status` and `git log --oneline -10`, and inspect the current project's actual code.
3. Do not trust earlier claims. Re-run tests before calling anything verified.

## While working

- Follow `MASTER_README.md` (lifecycle and definition of done) and `ARCHITECTURE_OVERVIEW.md`
  (layout, ports, environments, AI and security policy).
- Keep changes inside `PROJECT_NN/`, except for tracker and recovery updates.
- Progress goes in `projects.json` → `progress`. Then run
  `python shared-resources/scripts/render_docs.py`, and never hand-edit generated files.
- Commit at milestones with Conventional Commits scoped `project-NN`. Never commit secrets or
  databases, and never force-push.
- Never spend API credits or deploy publicly without the owner's explicit permission.
- Update the `recovery/` files before ending a session or finishing a project.
- **Credit the owner, Swayam, in every project:** an `**Author:** Swayam` line in the project
  README, a visible "built by Swayam" credit in the app UI, `author` / API-docs contact metadata,
  and "Swayam" as the demo account's display name.
- **After each project is complete, ask the owner for its data** using the project's
  `docs/YOUR_DATA.md` checklist. Non-secret data (lists, links, tasks, preferences) can be given in
  chat and loaded with the project's `scripts/import_data.py`. **Never ask for secrets in chat**
  (passwords, API keys, app passwords, private calendar links): the owner enters those in the app's
  own forms or in the project `.env`.
- **Every project gets a live preview** (owner's standing request): a one-command preview with demo
  data, a `project-NN-<slug>` entry in `.claude/launch.json`, and the running app opened in the
  Browser pane for the owner when the project is finished. If the owner asks to see a finished
  project again, start its preview. That is not a request to change the project.
