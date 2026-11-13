# Architecture: Habit & Routine Coach (Project 05), "Cadence"

## Overview

Cadence is one server-rendered Python process. FastAPI handles routing and form parsing, Jinja2
renders HTML, HTMX (vendored) upgrades a few actions in place, and SQLAlchemy talks to SQLite. No
Node build, no external database, no required network service.

```text
┌──────────────────────────────── Browser ────────────────────────────────┐
│ HTML forms · HTMX · app.js (toasts, confirmations) · CSS light/dark      │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │ HTTP :8005
┌───────────────────────────────────▼─────────────────────────────────────┐
│ FastAPI app (app/main.py)                                                │
│  middleware: CSP + nosniff + referrer policy                             │
│  error handlers: 404 / 422 / LoginRequired → HTML or HX-Trigger          │
│                                                                          │
│  routes/auth.py      register · login · logout                           │
│  routes/habits.py    dashboard · list · create · detail · update ·       │
│                      status · delete · log · coach · week                │
│  routes/reflect.py   reflect page/form · insights                        │
│  routes/settings.py  profile · password · export · delete                │
│                                                                          │
│  services/habitmath.py  schedules, streaks, rates, grids, reports        │
│  services/coach.py      deterministic rule suggestions                   │
│  services/ai.py         Claude JSON call → validate → fallback           │
│  services/charts.py     server-rendered HTML/CSS bars                    │
│                                                                          │
│  web.py      sessions, CSRF, template filters, auth dependencies         │
│  security.py scrypt hashing, token hashing, sliding-window limiter       │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ SQLAlchemy 2
                     ┌──────────▼──────────┐        ┌────────────────────┐
                     │ SQLite              │        │ Anthropic Messages │
                     │ data/cadence.db     │        │ API (optional)     │
                     └─────────────────────┘        └────────────────────┘
```

## Data model

```
users 1───n sessions
  │
  ├──1───n habits 1───n habit_logs   (unique habit_id + day)
  │            └───n suggestions
  └──1───n reflections               (unique user_id + week_start)
```

| Table | Columns | Notes |
|---|---|---|
| `users` | `id`, `email` (unique), `name`, `password_hash`, `timezone`, `created_at` | Timezone is an IANA name |
| `sessions` | `id`, `user_id` FK cascade, `token_hash` (unique), `csrf_token`, `created_at`, `expires_at` | Only the SHA-256 of the cookie token is stored |
| `habits` | `id`, `user_id` FK, `title`, `intention`, `cue`, `days`, `status`, `created_at`, `archived_at` | `days` is a comma-separated ISO weekday set, `0=Mon … 6=Sun`; index `(user_id, status)` |
| `habit_logs` | `id`, `user_id` FK, `habit_id` FK cascade, `day`, `status`, `note`, `created_at` | `status ∈ {done, skipped}`; unique `(habit_id, day)`; indexes `(user_id, day)` and `(habit_id, day)` |
| `reflections` | `id`, `user_id` FK, `week_start`, `mood`, `worked`, `friction`, `change`, `created_at` | Unique `(user_id, week_start)`, mood constrained to 1–5 |
| `suggestions` | `id`, `user_id`, `habit_id` FK cascade, `title`, `rationale`, `source`, `model`, `created_at` | `source ∈ {local, claude}`; index `(habit_id, created_at)` |

`UTCDateTime` in `db.py` normalises datetimes to UTC on the way in and out. Calendar days are
stored as `Date` in the user's local calendar; the timezone is only used to decide what "today" is.

Design choices:

- **No derived columns.** Streaks and rates are computed from logs on read. This avoids
  stale counters after an undo, a backfill or a schedule edit.
- **Planned rest is a log, not an absence.** `skipped` is explicit, so a blank day and a deliberate
  rest day are distinguishable forever.
- **Reflection upsert by week.** The unique key makes Sunday editing idempotent.

## Habit mathematics (`services/habitmath.py`)

| Function | Responsibility |
|---|---|
| `scheduled(habit, day)` | Whether the habit's weekday set contains `day.weekday()` |
| `log_map(logs)` | `{date: log}` for one habit |
| `streak(habit, logs, today)` | Consecutive scheduled days satisfied, walking backwards. Today unlogged is skipped; a scheduled day with no log before today ends the streak; `skipped` is neutral |
| `longest_streak` | Best historical run over the habit's life |
| `range_stats(habit, logs, start, end, today)` | `scheduled`, `done`, `skipped`, `missed`, `rate` where `rate = done / (done + missed)`, rounded. Today unlogged is neither missed nor decided |
| `habit_stats` | 7-day and 28-day stats, current/longest streak, created date |
| `calendar_status` | One of `done`, `missed`, `pending` (today, unlogged), `skipped`, `off`, `future` |
| `calendar_weeks` | Monday-first month grid padded with `None` |
| `week_grid` | Rows of habits × cells for one ISO week |
| `weekly_series` | Completed days per ISO week for the last N weeks |
| `weekday_pattern` | Done/scheduled and rate per weekday across N weeks |
| `habit_consistency` | Per-habit rate, streak and a read label (`steady`, `workable`, `shrink it`) |
| `reflection_streak` | Consecutive weeks reflected, tolerating an open current week |
| `weekly_report` | Rate, strongest routine, best day and sentence lines for the Week page |

Two rules are deliberately encoded in one place so every page agrees:

1. **Today is open.** `calendar_status` returns `pending` and `range_stats` excludes today from the
   decided denominator. The dashboard therefore shows 2 of 4 done without claiming 2 misses.
2. **Planned rest is neutral.** `skipped` never enters the numerator or denominator. Streaks walk
   through it.

Paused and archived habits are filtered at the route level before any statistics are computed, so
they cannot influence Week, Reflect or Insights.

## Coach pipeline (`services/coach.py`, `services/ai.py`)

```
habit + logs + today
        │
        ├─ rule_suggestions() ── always computed first (2–3 items)
        │
        ├─ no API key ──────────────▶ CoachResult(source="local", note="no key")
        │
        └─ key present
              POST /v1/messages (httpx, 30 s timeout, max_tokens bounded)
                    │
                    ├─ JSON parse + _validate() (2–4 items, 4–120 char title,
                    │   10–380 char rationale) ──▶ source="claude"
                    │
                    └─ network error / bad JSON / refusal / thin payload
                                                  ▶ local with a visible note
```

- The prompt allows only the supplied habit, schedule, recent 21 logs and computed stats. It
  forbids invented events and tells the model to shrink the habit rather than prescribe more
  effort.
- The response is parsed defensively: Markdown fences are tolerated, every field is trimmed and
  length-checked, and fewer than two valid items is a failure.
- `Suggestions` are persisted as rows with `source` and `model`, so the UI can label history
  honestly and the user can see which notes came from a model.
- The coach is rate-limited per user (`6 / 10 min`, in-memory sliding window) and the endpoint is
  CSRF-protected. Repeated failures never call the API in a loop.

## Routes and rendering

- `app/main.py` creates the app, runs Alembic, installs middleware and exception handlers, mounts
  `/static`, and includes four routers. The OpenAPI docs are disabled; the UI is the contract.
- Every page dependency `ctx` loads the user, session, timezone, local `today` and `week_start`.
  Anonymous visitors are redirected to `/login`; HTMX requests receive `HX-Redirect`.
- `optional_ctx` serves the login/register/error pages with the correct chrome.
- Actions use POST + `303 See Other`, then re-render from the database. This survives refreshes and
  keeps the browser's back button sane.
- HTMX is used for small in-place actions (log toggles, coach runs, filters) with a non-JS form
  fallback. `app.js` shows toasts for `app-error` events, confirms destructive actions and focuses
  invalid fields.
- Template filters (`datefmt`, `pct`, `schedule`, `dayname`) are registered once in `web.py`;
  `schedule` accepts either a habit object or a raw day string.

## Security

| Concern | Implementation |
|---|---|
| Passwords | `hashlib.scrypt` (N=2¹⁴, r=8, p=1), 16-byte random salt, constant-time compare |
| Sessions | 32-byte URL-safe token in `cd_session`; SHA-256 stored server-side; 30-day expiry; `HttpOnly`, `SameSite=Lax`, optional `Secure` |
| CSRF | Per-session token in a field and `X-CSRF-Token` header for HTMX; checked on every POST |
| Authorization | Every query scopes by `user_id`; a habit owned by another account returns 404 |
| Login abuse | 10 attempts / 15 min per client |
| Coach abuse | 6 runs / 10 min per user |
| Headers | CSP (`default-src 'self'`, no inline script), `nosniff`, `Referrer-Policy: same-origin`, `frame-ancestors 'none'` |
| Input | Pydantic forms, explicit length clamps, weekday parsing, IANA timezone validation, mood 1–5 |
| Secrets | `.env` git-ignored; database files git-ignored; no key required to run |
| Output | Jinja2 autoescaping; JSON export escapes nothing dangerous because it contains only user text |

## Migrations and operations

- One Alembic revision (`0001_initial_schema`) creates all tables, constraints and indexes.
- Startup calls `command.upgrade(cfg, "head")` unless `RUN_MIGRATIONS=false`. The same path is used
  by tests, the demo seed and the preview server, so no environment drifts.
- SQLite runs in WAL mode with foreign keys enabled (`db.py`). The database file is the only state.
- `scripts/preview.py` sets `DATABASE_URL` to `data/demo.db`, seeds it, then starts Uvicorn on
  `127.0.0.1:8005`. Real data in `cadence.db` is never touched.
- Backup is a file copy of the SQLite database while the app is stopped (or a `.backup` command).
- Logs go to stdout via `logging`, with the coach mode printed at startup and no passwords or
  tokens logged.

## Testing

76 pytest tests use a temporary SQLite file per test and FastAPI's `TestClient`. The shared
`Browser` helper keeps cookies, extracts the CSRF token, and posts forms the way the UI does.
Coverage is organised by boundary:

- **pure maths** (`test_habitmath.py`) for streaks, decided-day rates, pending today, calendars,
  weekday patterns and reflections;
- **routes** (`test_auth.py`, `test_habits.py`, `test_week.py`, `test_reflect_insights.py`,
  `test_settings.py`) for validation, ownership, redirects, exports and destructive actions;
- **AI safety** for schema validation and a forced network failure that must produce a labelled
  local fallback.

The visual layer was verified with real Playwright captures at desktop and mobile widths, including
dark mode. The screenshots in `docs/screenshots/` are outputs of that run.
