# PRD: Habit & Routine Coach (Project 05), "Cadence"

**Status:** Implemented in v1.0 (2026-11-13) · **Owner:** Swayam · **Category:** Personal Productivity & Life Management

## 1. Problem

Most habit trackers are built for the first two weeks. They reward a streak, punish a missed day
and quietly assume the user controls their calendar. When ordinary life interrupts — travel, a sick
child, a late meeting — the tracker turns a neutral event into a failure, then into a reason to stop
opening the app.

The second failure is subtler: a tracker that records only *whether* you did something teaches you
nothing about *why* it worked. The user can see a percentage but cannot answer "which day keeps
slipping?" or "what should I change on Monday?"

Cadence addresses both:

- A missed day is information, not a moral judgement. Planned rest is a first-class state.
- Today is never counted as missed while it is still open.
- Paused habits leave the reports instead of dragging the average down.
- A weekly reflection and a coach turn eight weeks of logs into one concrete change.

## 2. Target users

| User | Situation | What they need |
|---|---|---|
| The recovering perfectionist | Has abandoned three habit apps after a broken streak | A tracker where rest and a paused habit do not read as failure |
| The routine builder | Wants 2–5 stable routines (reading, walking, strength, journal) | A fast daily check-in, a week view and honest streaks |
| The reflective professional | Has enough discipline but a crowded week | Evidence about which weekdays fail, and one change to try |
| The privacy-conscious user | Will not send their daily behaviour to a SaaS | A local app with a local database and no mandatory cloud |

Primary persona: **a single organised adult who already has routines and wants to keep them
through a busy month**, not someone looking for a social challenge or a gamified streak leaderboard.

## 3. Use cases

1. **Morning check-in.** Open Today, see four routines, mark two done, leave two open.
2. **Evening catch-up.** Mark the remaining two done, or mark one as planned rest after a late night.
3. **Weekly review.** Open Week, notice Wednesday is consistently weak, read the report and reflect.
4. **Habit repair.** Ask the coach for a smaller version of the habit that keeps missing.
5. **Temporary pause.** Pause "No phone with breakfast" during a holiday; reports stop counting it.
6. **New routine.** Add "Evening journal", choose weekdays, write the cue, start today.
7. **Data ownership.** Export everything as JSON, or import an export into a fresh account.
8. **Account hygiene.** Change the password, change timezone, or delete the account completely.

## 4. MVP scope (implemented)

### Accounts and access
- Register with name, email and password; sign in and sign out.
- Password hashing, server-side sessions, `HttpOnly` cookie, CSRF on all mutations.
- Per-user isolation of every habit, log, reflection and suggestion.

### Habits
- Fields: title (required, ≤120), intention, cue, scheduled weekdays (at least one).
- Status: active, paused, archived.
- Create, edit, pause, resume, archive, delete (with confirmation).
- Habit list filtered by status.

### Daily logging
- One log per habit per calendar day, status `done` or `skipped` (planned rest).
- Set, change or clear a log for today from the dashboard or habit detail; any past day from the
  week grid or the habit calendar.
- Future days are not loggable.

### Calculations
- Current streak and longest streak over scheduled days.
- Seven-day and four-week rates using decided days (`done + missed`).
- Pending today: no log yet today is neither done nor missed.
- Month calendar with done / missed / pending / rest / not scheduled / future states.

### Week view
- Active habits × seven days; today highlighted.
- Click a cell to mark done, click again to undo; missed and pending cells can be filled.
- Previous/next week navigation; weekly report: completion, strongest routine, best day.

### Reflection
- One reflection per ISO week: mood 1–5, what worked, what got in the way, one change.
- Re-saving updates the same week; past reflections are listed.
- Reflection streak in weeks.

### Insights
- Eight-week completed-days chart.
- Completion by weekday with strongest/weakest day.
- Per-habit table: done, decided days, rate, streak, read label.
- "Honest read" paragraph and a next step linking to the week grid.

### Coach
- 2–3 suggestions per habit, stored with `source` and optional `model`.
- Claude path when a key exists; validated JSON; local deterministic path otherwise; every local
  note is visibly labelled.
- Six coach runs per ten minutes.

### Settings
- Display name and IANA timezone.
- Password change that invalidates other sessions.
- JSON export (`cadence-export-v1`).
- Account deletion requiring the password and the word `DELETE`.

### UI and operations
- Responsive desktop, tablet and phone layouts; light and dark themes.
- Empty states, error states, toasts, focus styles, print styles.
- `/health` endpoint, security headers, custom error pages.
- Alembic migration, demo seed, preview server and JSON importer.

## 5. Advanced features (post-MVP)

- Daily notes attached to a log entry and shown in habit history.
- Flexible schedules: every N days, N times per week, pause ranges.
- Monthly printable review combining grid and reflections.
- CSV import from other trackers.
- Optional local reminders without a paid service.
- Read-only JSON API for a native client.
- Shared-household accounts with per-user isolation (requires a real authorization model).

## 6. Out of scope

- Social feeds, leaderboards, public profiles or challenges.
- Push notifications, email reminders and password reset email.
- Paid AI, paid hosting, subscriptions or ads.
- Mobile native apps.
- Medical, therapeutic or clinical advice. The coach suggests habit design, not treatment.
- Multi-tenant hosting, team workspaces or administrator roles.

## 7. User stories

| # | As a… | I want to… | So that… |
|---|---|---|---|
| 1 | new user | create an account and add my first routine | I can start today without a tutorial |
| 2 | daily user | mark a routine done from the dashboard | checking in takes seconds |
| 3 | daily user | mark a planned rest day | a deliberate break does not look like a failure |
| 4 | busy user | leave today unmarked until evening | I am not punished for opening the app at noon |
| 5 | returning user | see my current streak | I know which routines are stable |
| 6 | reflective user | see which weekday is weakest | I can move or shrink the habit |
| 7 | reflective user | write one reflection per week | next week starts with one decision, not a vague intention |
| 8 | user with a slipping habit | ask for a smaller version | I repair the habit instead of abandoning it |
| 9 | user going on holiday | pause a habit | my reports stay meaningful while I am away |
| 10 | privacy-conscious user | export or delete all my data | I stay in control of my own records |
| 11 | user with a wrong clock/timezone | set my IANA timezone | "today" matches my actual day |
| 12 | user on a phone | use the week grid without a desktop | I can catch up from anywhere |

## 8. Key flows

### First run
`/register` → validation → session cookie → empty dashboard with "Add your first habit" → habit
form → today's schedule appears.

### Daily check-in
Dashboard → `Done` on a routine → `POST /habits/{id}/log` with `status=done`, `day=today`,
`next=/` → redirect → stats recomputed. `Undo` posts `status=clear`. `Rest` posts `status=skipped`.

### Weekly review
`/week` → scan grid → click a missed or pending cell → weekly report updates → "Reflect on this
week" → `/reflect?week=…` → mood and three answers → save → history and streak update.

### Habit repair
Habit detail → "Suggest a smaller ask" → rate limit check → local or Claude suggestions → stored
rows labelled `LOCAL` or `CLAUDE` → user edits the cue, schedule or size.

### Pause and resume
Habits → Paused filter → habit detail → Paused → habit leaves Today, Week and Insights; history is
preserved → Resume returns it to the current schedule without backfilling missed days.

### Data portability
Settings → Download JSON → file `cadence-export.json` → optional `import_data.py` into another
account → duplicate habits/logs/reflections are skipped.

## 9. Non-functional requirements

| Area | Requirement |
|---|---|
| Performance | Dashboard and week render in well under a second for 50 habits × 1 year of logs on a laptop; SQLite with indexes on `(user_id, day)` and `(habit_id, day)` |
| Security | Hashed passwords, hashed session tokens, CSRF, CSP and security headers, per-user authorization, no secrets in the repository |
| Privacy | Local-only by default; no analytics, no third-party scripts; Claude is opt-in and receives only habit/log/stat data, never the password or email |
| Accessibility | Semantic headings, labelled form controls, visible focus, keyboard-operable buttons, respect for reduced motion, contrast checked in both themes |
| Reliability | Alembic migrations on startup, deterministic seed, graceful AI fallback, consistent 404/422 pages, no data loss on failed form submissions |
| Portability | One Python process; no Node build; works on Windows, macOS and Linux; SQLite file is the only state |
| Maintainability | Routes → services → models separation; one responsibility per module; tests for every calculation and route family |

## 10. Success criteria

A release is complete only when all of the following are true:

- [x] A new account can register, add habits, log days and see correct streaks.
- [x] Planned rest and pending today never count as misses.
- [x] Paused habits do not appear in Week, Reflect or Insights.
- [x] Week grid can mark and unmark days, and refuses future days.
- [x] One reflection per week is saved, editable and included in the streak.
- [x] Insights numbers are derived from logs, not seeded display values.
- [x] Coach returns validated suggestions with an honest source label, or falls back safely.
- [x] Export contains habits, logs and reflections and no password material.
- [x] Account deletion removes access and invalidates the session.
- [x] 76 automated tests pass on a clean database.
- [x] Screenshots are captured from the running app, not mocked.
- [x] README, PRD, architecture and data guide are complete.
