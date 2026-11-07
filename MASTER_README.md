# Programme Handbook

How the 50 projects are planned, built, verified and published. The [README](README.md) is
the public overview; this file holds the working rules.

## 1. Execution control (project-manager rules)

The repository owner is the project manager and decides **when** each project starts. The
developer decides **how** to build it.

- No project starts without the owner's explicit command, in the form **`Start Project N`**.
- Only the authorized project is worked on. Fixing or changing an existing project also needs
  an explicit request that names it.
- When a project is complete, verified and published, work **stops** until the next command.
- General discussion, questions and progress updates are not permission to start or continue
  a project.
- After a lost session or context reset, state is recovered from [`recovery/`](recovery/), and
  work on the current project resumes only when the owner says to continue.

The current authorization is always recorded in
[`recovery/CURRENT_STATE.md`](recovery/CURRENT_STATE.md) under **Authorized project**.

## 2. Lifecycle for every project

| Phase | Output |
|---|---|
| A. Product planning | `docs/PRD.md`: problem, target users, use cases, MVP vs advanced features, user stories, user flows, data model, stack choice, task breakdown |
| B. UI/UX design | Responsive layouts, consistent type and colour tokens, loading, empty, error and success states, confirmation dialogs, accessible controls |
| C. Frontend | Modular components, routing, state, validated forms, real API calls. Every visible control does something real |
| D. Backend | Validated endpoints, consistent errors, auth where the app holds personal data, logging |
| E. Database | Real persistence with models, relations, migrations and indexes. Demo data lives in a clearly labelled seed script |
| F. AI integration | Only where it adds value. Real API calls, validated outputs, error handling, a labelled fallback, documented limits |
| G. Testing | Unit, API/integration and DB tests, plus frontend and user-flow tests where they make sense. The app is run locally and checked |
| H. Documentation | Project README (15 required sections), `docs/ARCHITECTURE.md`, real screenshots |

### Definition of done

A project is marked **Completed** only when all of these are true:

1. The core features from the source brief work in the running app and have been checked by hand.
2. The automated test suite passes, and the README states the exact command and result.
3. Nothing is presented as working when it is not. Unverified integrations (for example, ones that
   need credentials that were never supplied) are listed under *Known limitations*.
4. The README, architecture doc, `.env.example` and screenshots are present.
5. The project has a **one-command live preview** with clearly labelled demo data, an entry in
   `.claude/launch.json`, and the owner has been shown it running in the Browser pane.
6. A secrets scan is clean and work is committed with a `release(project-NN)` commit and a
   `project-NN-v1.0` tag.
7. `projects.json` is updated and the docs are regenerated.

GitHub publication is tracked separately. A project can be complete locally while its push is blocked.

## 3. Per-project workflow checklist

1. Record the authorization in `recovery/CURRENT_STATE.md`.
2. Write the PRD and architecture docs, then commit them (`docs(project-NN): ...`).
3. Build feature by feature and commit at each milestone (`feat(project-NN): ...`).
4. Write and run tests (`test(project-NN): ...`), then fix what fails.
5. Run the app, check every core flow, and capture screenshots.
6. Finish the README and set the status in `projects.json`, then run
   `python shared-resources/scripts/render_docs.py`.
7. Scan for secrets, commit `release(project-NN): ...`, and tag `project-NN-v1.0`.
8. Push to GitHub and check the files appear there.
9. Open the live preview for the owner in the Browser pane (`preview_start` with the project's
   `.claude/launch.json` entry), signed in to the demo account where the app needs one.
10. Update every file in `recovery/` with the final state. **Stop and report.**

## 4. Quality bar

**Prioritize:** clean architecture, secure defaults, real persistence, working integrations,
automated tests, honest documentation, AI used only where it adds value.

**Avoid:** static mockups shown as products, fake AI responses, buttons that do nothing,
hardcoded live-looking data, untested completion claims, needless complexity.

Stacks are chosen per project to fit its needs. Not every project uses the same stack.

## 5. Spending and external actions

- No paid API credits are used without the owner's explicit permission. AI features are built
  and tested with mocked clients. Live calls happen only with the owner's own key and approval.
- Nothing is deployed publicly without approval.
- No force-pushes, and no deleting or overwriting existing repositories.

## 6. Key files

| File | Purpose |
|---|---|
| [`projects.json`](projects.json) | Source of truth for names, categories, stacks and progress |
| [`MASTER_PROJECT_TRACKER.md`](MASTER_PROJECT_TRACKER.md) | Generated phase-by-phase tracker |
| [`PROJECT_INDEX.md`](PROJECT_INDEX.md) | Generated detailed index |
| [`ARCHITECTURE_OVERVIEW.md`](ARCHITECTURE_OVERVIEW.md) | Conventions shared by every project |
| [`DEVELOPMENT_LOG.md`](DEVELOPMENT_LOG.md) | Decisions, dependency changes, bugs and fixes |
| [`recovery/`](recovery/) | State needed to resume after an interruption |
