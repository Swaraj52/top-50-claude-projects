# Foundry: Business Operations Hub

**Foundry** is a local-first Business Operations Hub built with FastAPI, Jinja2, HTMX, and SQLite. It helps teams manage SOPs (Standard Operating Procedures), process checklists, and ownership tracking in one working handbook.

## Key Features

- **SOP Library**: Manage SOPs with codes, purpose, scope, area, owner, cadence, review windows, and versioned steps
- **Process Checklists**: Run checklists snapshotted from SOP steps with progress tracking, due dates, and overdue detection
- **Ownership Dashboard**: Track people, coverage, area×person matrix, and unowned lists
- **Dashboard Next Moves**: View what needs attention across SOPs and runs
- **Optional SOP Drafting**: Generate bounded SOP drafts from descriptions (using local logic or Claude API)
- **Export/Import**: Export SOPs, steps, runs, and items in `foundry-export-v1` format; idempotent import

## Design Language

- Warm workshop paper background with graphite text
- Safety-orange accent color
- Stencil/mono labels and dashboard rules
- Top masthead with dashed navigation rules
- Responsive layout (works at 1440px desktop and 390px phone)

## Architecture

- **Local-first**: All data stored in SQLite, no external dependencies required
- **No paid services**: Free-only model policy
- **Authentication**: Form-based with session cookies, CSRF protection, password validation
- **Authorization**: User-owned SOPs and runs; ownership tracked via people table
- **Bounded drafting**: Optional SOP generation from descriptions, no uncrawled data

## Quick Start

1. Activate the shared venv: `..\\shared-resources\\.venv\\Scripts\\activate`
2. Start the server: `python -m app.main`
3. Visit `http://127.0.0.1:8010`
4. Login with: `demo@foundry.example` / `demo-password`

## Screenshots

![Foundry Desktop Light](screenshots/foundry-light-1440.png)
![Foundry Desktop Dark](screenshots/foundry-dark-1440.png)
![Foundry Phone](screenshots/foundry-phone-390.png)

## Built by Swayam

Credits for the application go to Swayam Naik.