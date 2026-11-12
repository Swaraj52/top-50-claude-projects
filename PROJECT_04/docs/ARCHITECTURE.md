# Architecture: Personal Goal Tracker (Project 04), "Summit"

## Overview

```text
Browser ──HTML forms / HTMX──▶ FastAPI (Jinja2 templates)
                                 ├── routes: auth, goals (dashboard, goals, milestones,
                                 │           check-ins, coach), weekly (plan, carry),
                                 │           insights (charts, review), settings
                                 ├── services: goalmath (progress, pace, series),
                                 │             coach (deterministic plan), ai (Claude or fallback),
                                 │             charts (HTML bars + SVG line)
                                 └── SQLAlchemy ──▶ SQLite (data/summit.db), Alembic migrations
                                                └──▶ Claude Messages API (optional)
```

One process on port **8004** serves pages, HTMX fragments and static files (`app/static`, including
a vendored `htmx.min.js`). There is no Node toolchain. Every page works without JavaScript: forms
post and redirect. HTMX upgrades action toggles to an in-place fragment swap.

## Data model

```text
users(id, email UNIQUE, name, password_hash, timezone, weekly_capacity_min, created_at)
sessions(id, user_id → users, token_hash UNIQUE, csrf_token, created_at, expires_at)
goals(id, user_id → users, title, description, why, category, status, target_date?, created_at, achieved_at?)
milestones(id, goal_id → goals, title, detail, due_date?, weight 1..5, position, status, completed_at?)
weekly_actions(id, user_id → users, goal_id → goals, milestone_id? → milestones, title,
               estimate_min 5..600, week_start DATE, status[open|done|skipped],
               source[manual|coach], done_at?, created_at)
checkins(id, user_id → users, goal_id → goals, day DATE, confidence 1..5, note,
         created_at, UNIQUE(goal_id, day))
```

Every user-owned row carries either `user_id` or a `goal_id` whose goal is scoped to the user.
Queries always filter by the signed-in user; another user's row returns 404, never a permission
leak. Deleting a user cascades through sessions, goals, milestones, actions and check-ins.

`week_start` is always a Monday (`monday_of`), stored as a `DATE`, which makes "this week" and
carry-over exact. "Today" and "this week" are computed in the user's IANA timezone
(`timeutil.local_today`, `monday_of`), not in UTC.

## Goal mathematics (`services/goalmath.py`)

- **Weighted progress:** `round(100 × done weight / total weight)`. Milestones with no weight
  default to 1; a goal with no milestones returns 0 and is labelled *setup*.
- **Next milestone:** open milestones ordered by `(no due date, due date, position, id)`.
- **Pace:** expected progress interpolates from the goal's creation date to its target date,
  clamped to 0–100. `delta = actual − expected`; `≥ +10` ahead, `≥ −10` on track, otherwise behind.
  A passed target with `< 100%` is overdue. Closed goals are not paced.
- **At risk:** active, and either behind/overdue, or ≤ 21 days left with under 60% done.
- **Weekly series:** counts of done and open actions per week for the last 6 (dashboard) or 8
  (insights) weeks. Skipped actions are excluded from the denominator.
- **Confidence series:** check-ins bucketed by the Monday of their week, averaged; empty weeks stay
  `None` so the line shows a gap instead of a false zero.
- **Streak:** consecutive days with at least one check-in, ending today or yesterday (so a
  not-yet-checked-in day does not break the streak in the morning).
- **Category summary and health rows:** average progress per category; active goals sorted with
  at-risk first, then by days left.

## Coach pipeline (`services/coach.py`, `services/ai.py`)

1. **Local plan always runs.** It considers open milestones (nearest first), the latest check-in,
   and pace. It emits 3–5 suggestions: advance the next two milestones, a scope decision when
   behind, a small reset when confidence is ≤ 2, a first check-in when none exists, or setup
   actions when there are no milestones. Titles are de-duplicated and estimates come from
   milestone weight (30–90 minutes).
2. **Claude is optional.** With `ANTHROPIC_API_KEY`, Summit sends one Messages API request to the
   configured model with a strict system prompt: 3–5 actions, 10–120 minutes each, reference only
   supplied milestones, return JSON only. The payload contains the goal, its description and why,
   category, target date, computed progress and pace, milestones (id, title, weight, status, due
   date) and the six most recent check-ins.
3. **Validation.** The response is parsed as JSON and every action is checked: title 4–120
   characters, non-empty rationale, estimate clamped to 10–120, `milestone_id` must be in the
   supplied set (otherwise `null`). Fewer than two valid actions is a failure. Markdown fences are
   tolerated.
4. **Fallback.** Any exception — network, HTTP status, refusal, unreadable JSON, validation — logs
   a warning and returns the local plan with a visible note naming the failure type. The app never
   claims Claude wrote something it did not.
5. **Cost and abuse control.** One coach call is one billed request when a key is present. A
   sliding-window limiter allows six calls per user per ten minutes. Suggestions are immediately
   filed as `weekly_actions` with `source="coach"` for the current week, and can be edited or
   deleted like any other action.

## Weekly plan (`routes/weekly.py`)

- `GET /weekly?week=YYYY-MM-DD` snaps the date to Monday, loads that week's actions grouped by goal,
  and shows planned minutes against the user's weekly capacity.
- Previous/next links are pure dates; no state is hidden in the session.
- Toggle marks `done`/`open` and sets `done_at`; HTMX returns `partials/action_row.html`, a plain
  form redirects back to the same week.
- Delete is scoped to the owner and returns to the action's week.
- Carry copies last week's *open* actions into the selected week, skipping any title already present
  in the destination. It deliberately copies instead of moving, so history stays honest.

## Charts (`services/charts.py`)

- **Bars** are plain HTML/CSS (`.bars`, `.bar-col`, `.bar`) so values and labels stay crisp at any
  width and never depend on JavaScript. The dashboard and insights share the same component.
- **The confidence line** is an SVG path in a `0 0 100 100` viewBox with
  `preserveAspectRatio="none"`: geometry stretches, while stroke width is preserved with
  `vector-effect="non-scaling-stroke"`. Dots and week labels are HTML positioned by percentage, so
  they keep their shape and readable size. Empty weeks produce gaps.
- Every chart has an accessible name and the underlying numbers appear as text, so the page is
  usable without seeing colour or geometry.

## Routes and rendering

| Area | Routes |
|---|---|
| Auth | `GET/POST /login`, `GET/POST /register`, `POST /logout` |
| Dashboard | `GET /` |
| Goals | `GET /goals`, `POST /goals`, `GET /goals/{id}`, `POST /goals/{id}/update`, `POST /goals/{id}/status`, `POST /goals/{id}/delete` |
| Milestones | `POST /goals/{id}/milestones`, `POST /milestones/{id}/toggle`, `POST /milestones/{id}/delete` |
| Check-ins | `POST /goals/{id}/checkins` |
| Coach | `POST /goals/{id}/coach` |
| Weekly | `GET /weekly`, `POST /weekly/actions`, `POST /weekly/actions/{id}/toggle`, `POST /weekly/actions/{id}/delete`, `POST /weekly/carry` |
| Insights | `GET /insights`, `GET /goals/{id}/review` |
| Settings | `GET/POST /settings`, `POST /settings/password`, `GET /settings/export`, `POST /settings/delete` |
| Health | `GET /health` |

Errors are rendered as an HTML page for normal requests and as a toast (`HX-Trigger`) for HTMX
requests. A signed-out page request redirects to `/login`.

## Security

- **Passwords:** scrypt (N=16384, r=8, p=1) with a random salt; constant-time comparison.
- **Sessions:** 32-byte URL-safe token in an HttpOnly, SameSite=Lax cookie (Secure when configured).
  Only the SHA-256 hash is stored. Sessions expire after `SESSION_DAYS`.
- **CSRF:** a per-session synchronizer token embedded in every form and sent as `X-CSRF-Token` on
  HTMX requests (`hx-headers` on `<body>`), checked with a constant-time compare on all unsafe
  methods. Signed-out forms use a double-submit cookie.
- **Rate limits:** login attempts (10 per 15 minutes per email/IP key) and coach calls (6 per 10
  minutes per user), both in-memory sliding windows.
- **Scoping:** every query filters by `user_id`; missing rows are 404. Milestone and action
  ownership is checked through their goal.
- **Output:** Jinja2 autoescaping for all user content; notes and titles are length-limited and
  whitespace-collapsed.
- **Headers:** Content-Security-Policy (`script-src 'self'`), `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: same-origin`, `frame-ancestors 'none'`.

## Migrations and operations

- Alembic revision `0001_initial_schema` creates all tables, checks and indexes. `run_migrations`
  runs at startup when `RUN_MIGRATIONS=true`; tests compare the migrated schema with the models.
- SQLite lives in `PROJECT_04/data/summit.db`; the demo uses `data/demo.db` so real data is never
  touched by `scripts/preview.py`.
- `scripts/seed_demo.py` recreates only the demo account with eight weeks of actions and check-ins;
  it is safe to run repeatedly.
- `scripts/import_data.py` loads a Summit JSON export (or the same hand-written shape), validates
  every goal before saving, skips duplicate goal titles and can run with `--dry-run`.

## Testing

pytest + FastAPI TestClient with a temporary SQLite database per test. Coverage includes auth and
CSRF rejection, per-user isolation, goal and milestone lifecycle, weighted progress and pace maths,
check-in upsert, weekly action lifecycle and carry-over, HTMX fragment responses, coach planning
and validation (including a fake Claude client with invented milestone ids), insights rendering,
settings/password/export/deletion, security headers and migration-model parity.
