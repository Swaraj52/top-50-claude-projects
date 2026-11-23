# Foundry - Architecture Document

## Overview
Foundry is a Business Operations Hub built with a modular, clean architecture pattern. The application is entirely local-first with no external dependencies.

## Technology Stack

- **Framework**: FastAPI (Python 3.13)
- **Templates**: Jinja2
- **Frontend**: HTMX for dynamic updates, no JavaScript framework required
- **Database**: SQLite with Alembic migrations
- **Static Files**: CSS, JS, favicon served from `/static` directory
- **Authentication**: Form-based with session cookies, CSRF protection
- **ORM**: SQLAlchemy 2.0 style with `Mapped` and `mapped_column`

## Directory Structure

```
PROJECT_10/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py          # FastAPI app creation
│   │   ├── config.py        # Settings/configuration
│   │   ├── db.py            # Database engine and session management
│   │   ├── models.py        # SQLAlchemy models and constants
│   │   ├── security.py      # Password hashing, token generation
│   │   ├── timeutil.py      # Timezone handling, relative dates
│   │   ├── web.py           # Request helpers, CSRF, template rendering
│   │   ├── routes/          # API routes (auth, dashboard, sops, steps, runs, people, ownership, settings)
│   │   ├── services/        # Business logic (sops, runs, ownership, overview, draft)
│   │   └── forms.py         # Form validation helpers
│   ├── alembic/             # Database migrations
│   ├── tests/               # pytest test suite
│   └── scripts/             # Seed and utility scripts
├── data/                    # SQLite database (data/foundry.db)
├── docs/                    # Documentation (README, PRD, ARCHITECTURE, YOUR_DATA)
├── .claude/                 # OpenCode configuration
└── projects.json            # Project tracking
```

## Data Flow

1. **HTTP Request** → FastAPI route → `ctx` dependency → gets `Ctx` (user, session, timezone, today, now)
2. **Business Logic** → Service functions (sops, runs, ownership, overview, draft) → SQLAlchemy queries
3. **Template Rendering** → `render()` function → Jinja2 template with `Ctx` data and CSRF token
4. **Response** → HTML sent back to browser, HTMX updates partial areas

## Authentication Flow

1. **GET /login**: If already authenticated, redirect to `/`. Otherwise, render login form with `fd_csrf` cookie set.
2. **POST /login**: 
   - `pre_csrf` dependency checks form `csrf_token` matches `fd_csrf` cookie
   - Verify email/password against database
   - `_sign_in`: Create session, set `fd_session` cookie, delete `fd_csrf` cookie, redirect to `/`
3. **GET /register**: Render registration form
4. **POST /register**: `pre_csrf` dependency checks form `csrf_token` matches `fd_csrf` cookie
   - Validate inputs, create user, `_sign_in`, redirect to `/`
5. **POST /logout**: `csrf` dependency validates session, delete `fd_session` cookie, redirect to `/login`

## SOP Data Model

### Users
- id, email (unique), name, password_hash, timezone, created_at

### Sessions
- id, user_id (FK→users), token_hash (unique), csrf_token, created_at, expires_at
- Foreign key with ondelete=CASCADE

### People
- id, user_id (FK→users), name, role, email, notes, active, created_at
- Unique constraint: (user_id, name)
- Index: (user_id, active)

### SOPs
- id, user_id (FK→users), code (unique within user), title, area, purpose, scope
- owner_id (FK→people, ondelete=SET NULL), cadence, review_months, last_reviewed_on, version
- Status: draft, active, retired
- Check constraints: area, status, cadence, review_months

### SopSteps
- id, sop_id (FK→sops), position, title, detail, role, minutes, created_at
- Unique constraint: (sop_id, position)

### Runs
- id, sop_id (FK→sops), owner_id (FK→people, ondelete=SET NULL), started_on, due_on
- Status: open, done, abandoned
- Notes, completed_at, created_at

### RunItems
- id, run_id (FK→runs), position, title, detail, role, done, done_at, note, created_at
- Unique constraint: (run_id, position)

## Constants

### AREAS
(`sales`, `delivery`, `finance`, `people`, `operations`, `product`)

### SOP_STATUSES
(`draft`, `active`, `retired`)

### CADENCES
(`daily`, `weekly`, `monthly`, `quarterly`, `ad_hoc`)

### REVIEW_MONTHS
(1, 3, 6, 12)

### RUN_STATUSES
(`open`, `done`, `abandoned`)

### MAX_STEPS
40 (maximum steps allowed per SOP)

## CSS Design System

- **Background**: Warm workshop paper color (#fdf6e9)
- **Text**: Graphite gray (#333333)
- **Accent**: Safety orange (#ff6b35)
- **Stencil labels**: Mono-spaced font, safety orange accent
- **Masthead**: Dashed navigation rules, brand mark SVG
- **Responsive**: Max-width 1440px desktop, fluid below; 390px phone width, no horizontal scroll

## API Endpoints (summary)

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Desk dashboard |
| `/login` | GET/POST | Login page/form |
| `/register` | GET/POST | Register page/form |
| `/sops` | GET/POST | SOP library |
| `/sops/new` | POST | Create new SOP |
| `/sops/{id}` | GET | SOP detail |
| `/runs` | GET | Checklist runs |
| `/runs/new` | POST | Create new run |
| `/people` | GET/POST | People management |
| `/ownership` | GET | Ownership dashboard |
| `/settings` | GET/POST | User settings |
| `/settings/password` | POST | Change password |
| `/settings/export` | GET | Export foundry-export-v1 JSON |
| `/settings/delete` | POST | Delete account |

## Deployment

- **One-command preview**: `python -m app.main` starts server on port 8010
- **Shared venv**: `shared-resources/.venv` is a junction/junction point
- **Per-app venv**: Each `backend/.venv` is a junction to the shared venv
- **No deployment**: Application is local-only, no public deployment allowed