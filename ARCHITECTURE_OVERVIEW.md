# Architecture Overview

Conventions that every project in this repository follows. Each project's own
`docs/ARCHITECTURE.md` covers its specific design.

## Repository model

One Git repository holds all 50 projects. The projects are **not** coupled to each other: each
has its own dependency manifest, environment, database and test suite, and can be copied out and
run alone. Nothing at the root is needed to run a project, except the optional documentation tooling.

## Standard project layout

The layout adapts to the project. A typical full-stack project looks like this:

```text
PROJECT_NN/
├── README.md              # full project documentation (15 sections)
├── .env.example           # every config key, no real values
├── docs/
│   ├── PRD.md             # product requirements
│   ├── ARCHITECTURE.md    # stack, data model, API, flows, decisions
│   └── screenshots/       # real captures of the running app
├── backend/               # API service (when the project needs one)
│   ├── app/ or src/
│   ├── tests/
│   └── requirements.txt | pyproject.toml | package.json
└── frontend/              # web UI (when the project needs one)
    ├── src/
    ├── tests/ or src/**/*.test.*
    └── package.json
```

Single-process projects, such as a CLI or a Python app that serves its own UI, skip the
`backend/` / `frontend/` split.

## Environment isolation

| Concern | Rule |
|---|---|
| Python | A per-project virtualenv at `PROJECT_NN/<service>/.venv` (git-ignored). Dependencies are pinned in that project's manifest |
| Node.js | A per-project `package.json` and lockfile. `node_modules/` is git-ignored |
| Database | A separate database per project. For SQLite, the file lives under the project's `data/` folder, is git-ignored, and is created by migrations on first run |
| Config | A per-project `.env` (git-ignored), documented by a committed `.env.example` |
| Docker | Added only when it makes a project easier to reproduce, for example when it needs Postgres or Redis |

## Port allocation

Each project reserves two ports so any number of projects can run side by side:

| Service | Port | Example (Project 07) |
|---|---|---|
| Backend / API | `8000 + N` | `8007` |
| Frontend dev server | `5100 + N` | `5107` |

Ports can be overridden through the project's `.env`.

## Baseline toolchain (verified 2026-11-07)

| Tool | Version on the development machine |
|---|---|
| Python | 3.13.7 |
| Node.js | 24.11.0 |
| npm | 11.6.1 |
| Git | 2.51.2 |

Projects state their own minimum versions, usually Python 3.11+ and Node 20+.

## Live previews

Every project can be previewed with one command that starts it with clearly labelled demo data,
without touching the user's real data (a separate demo database or folder). The command is
documented in the project README, and the workspace's [`.claude/launch.json`](.claude/launch.json)
has a matching `project-NN-<slug>` entry so it can be opened in the Claude desktop Browser pane.

| Project | Preview command | URL |
|---|---|---|
| 01 Personal Dashboard | `python PROJECT_01/backend/scripts/preview.py` (after `npm run build` in `frontend/`) | http://127.0.0.1:8001 |

## AI integration policy

- Use AI only where it beats ordinary code. Summaries, drafting, extraction and semantic search
  are good fits. Arithmetic, sorting and CRUD are not.
- Make real API calls only. The key comes from the project's `.env`, for example
  `ANTHROPIC_API_KEY`, and is never committed or logged.
- Request structured output where possible and validate it against a schema before using it.
  Handle timeouts, rate limits and malformed responses.
- If AI is not configured, either switch the feature off with a clear message or use a
  deterministic fallback that the UI labels as non-AI. A fallback is never passed off as AI output.
- Test with mocked clients, so test runs never spend credits. Live calls need the owner's key and
  permission, and the README records whether they were verified.
- Document each project's model choice, prompt design and limitations in its architecture doc.

## Security baseline

- Apps that store personal data require authentication, and every query is scoped to the
  signed-in user.
- Passwords are hashed with a slow KDF (scrypt, argon2 or bcrypt). Sessions use HttpOnly cookies
  or short-lived tokens.
- Third-party credentials that must be stored, such as an IMAP app password, are encrypted at
  rest with a key from `.env`.
- All input is validated at the API boundary, and error responses are consistent and leak
  nothing sensitive.
- Outbound fetches of user-supplied URLs are limited to http(s), with timeouts and size caps.
- Before every commit and push: no `.env` files, keys, tokens, personal data or real databases.

## Shared resources

[`shared-resources/`](shared-resources/) holds code and tooling used by more than one project.
A component is added there only when at least two projects need it. It must document its
interface, its dependencies and the projects that use it. Projects copy or vendor what they use,
so each one still runs on its own.

## Documentation generation

[`projects.json`](projects.json) is the source of truth for project metadata and progress.
`python shared-resources/scripts/render_docs.py` regenerates the tracker, the index, the README
project tables and any placeholder project READMEs. `--check` reports stale files without
writing anything.
