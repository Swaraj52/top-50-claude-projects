# Architecture — Personal Dashboard (Project 01)

## Overview

```text
 Browser (React SPA)                      FastAPI backend (Python 3.11+)              Storage / external
┌──────────────────────┐  /api (JSON,    ┌───────────────────────────────┐          ┌──────────────────┐
│ Dashboard · Tasks ·  │  cookie session)│ routers/  auth tasks reminders│  SQLAlch.│ SQLite            │
│ Calendar · Inbox ·   │ ───────────────▶│ events calendars email        │ ───────▶ │ data/dashboard.db │
│ Settings · Ctrl+K    │                 │ priorities dashboard briefing │          └──────────────────┘
│ TanStack Query cache │ ◀─────────────── │ services/ ics imap briefing   │ ───────▶ ICS feeds (https)
└──────────────────────┘                 │ security (scrypt, sessions,   │ ───────▶ IMAP server (TLS)
                                         │  Fernet, CSRF, rate limit)    │ ───────▶ Claude API (optional)
                                         └───────────────────────────────┘
```

In development Vite (port 5101) proxies `/api` to Uvicorn (port 8001). In production the backend
also serves the built SPA from `frontend/dist`, so the whole app is one process on port 8001.

## Technology choices

| Layer | Choice | Why |
|---|---|---|
| API | FastAPI + Pydantic v2 | Typed request validation, automatic OpenAPI docs at `/docs` |
| ORM / DB | SQLAlchemy 2.0 + SQLite | Zero-setup local persistence; SQLAlchemy keeps a Postgres move cheap |
| Migrations | Alembic | Versioned schema; applied automatically at startup |
| Calendar | `icalendar` + `recurring-ical-events` | Correct RRULE/EXDATE/timezone expansion of real ICS feeds |
| Email | stdlib `imaplib` (read-only, `BODY.PEEK`) | No extra dependency; never marks mail as read |
| Secrets at rest | `cryptography` Fernet | Authenticated symmetric encryption keyed by `APP_SECRET_KEY` |
| AI | `anthropic` SDK, `claude-opus-5-5` | Structured JSON output validated with Pydantic; optional |
| Frontend | React 18 + TypeScript + Vite | Fast dev loop, typed API layer |
| Data fetching | TanStack Query | Caching, background refetch, mutation invalidation |
| Date parsing | `chrono-node` | Robust natural-language dates for quick-add |
| Tests | pytest (+ FastAPI TestClient), Vitest + Testing Library | API, service and UI logic coverage |

## Data model

```text
users(id, email UNIQUE, name, password_hash, timezone, created_at)
sessions(id, user_id→users, token_hash UNIQUE, created_at, expires_at)
tasks(id, user_id, title, notes, priority[low|medium|high], status[todo|done],
      due_date DATE?, completed_at?, source_email_id?, created_at, updated_at)
reminders(id, user_id, text, remind_at UTC, status[pending|dismissed], task_id?, created_at)
calendar_sources(id, user_id, name, kind[url|file], url_encrypted?, color,
                 last_synced_at?, last_error?, event_count, created_at)
events(id, user_id, source_id?→calendar_sources (NULL = local event), uid, title, location,
       description, start_at UTC, end_at UTC, all_day, created_at)
email_accounts(id, user_id UNIQUE, host, port, username, password_encrypted, mailbox,
               last_synced_at?, last_error?, created_at)
emails(id, user_id, account_id→email_accounts, uid, message_id, from_name, from_addr,
       subject, received_at UTC, is_unread, is_flagged, UNIQUE(account_id, uid))
daily_priorities(id, user_id, day DATE, position 1..3, text, task_id?, done,
                 UNIQUE(user_id, day, position))
briefings(id, user_id, day DATE, source[ai|rule], model?, content JSON, created_at)
```

All timestamps are stored in UTC. "Today", "overdue" and the agenda are computed in the user's
IANA timezone (`users.timezone`, defaulted from the browser at sign-up). Every query is filtered by
`user_id`; a record owned by someone else returns **404**, never 403, so ids are not enumerable.
Deleting a calendar source cascades to its events; deleting the email account cascades to emails.

## API surface (`/api`)

| Area | Endpoints |
|---|---|
| Meta | `GET /health`, `GET /meta` (version, AI enabled, model) |
| Auth | `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`, `PATCH /auth/me` |
| Tasks | `GET /tasks?view=today\|overdue\|upcoming\|all\|done`, `POST /tasks`, `PATCH /tasks/{id}`, `DELETE /tasks/{id}` |
| Reminders | `GET /reminders`, `GET /reminders/due`, `POST /reminders`, `PATCH /reminders/{id}`, `POST /reminders/{id}/snooze`, `POST /reminders/{id}/dismiss`, `DELETE /reminders/{id}` |
| Events | `GET /events?start&end`, `POST /events`, `PATCH /events/{id}`, `DELETE /events/{id}` (synced events are read-only → 409) |
| Calendars | `GET /calendars`, `POST /calendars` (URL), `POST /calendars/upload` (.ics), `POST /calendars/{id}/sync`, `DELETE /calendars/{id}` |
| Email | `GET/PUT/DELETE /email/account`, `POST /email/sync`, `GET /email/messages?filter=attention\|unread\|all`, `POST /email/messages/{id}/task` |
| Priorities | `GET /priorities?day`, `PUT /priorities` (replace the day's list), `PATCH /priorities/{id}` |
| Dashboard | `GET /dashboard/today` (one round-trip for the whole home screen) |
| Briefing | `GET /briefing/today`, `POST /briefing` |

Errors always have the shape `{"detail": "<message>"}` (plus `errors` for validation failures).
Interactive docs: `http://localhost:8001/docs`.

## Security

- **Passwords:** scrypt (n=2¹⁴, r=8, p=1, 16-byte salt) via `hashlib.scrypt`; constant-time compare.
- **Sessions:** 32-byte random token in an `HttpOnly`, `SameSite=Lax` cookie (`Secure` when
  `COOKIE_SECURE=true`); only its SHA-256 is stored; 14-day expiry; logout deletes the row.
- **CSRF:** every non-GET `/api` request must carry `X-Requested-With: dashboard` — a header a
  cross-site form cannot set — on top of `SameSite=Lax`.
- **Brute force:** login is limited to 10 failures per email+IP per 15 minutes (HTTP 429).
- **Secrets at rest:** IMAP passwords and private ICS URLs are Fernet-encrypted with a key
  derived from `APP_SECRET_KEY`; they are never returned by the API.
- **Outbound fetch (ICS URLs):** `http(s)` only, 15 s timeout, 5 MB cap, no credentials forwarded.
- **AI:** only the minimum day context is sent (titles, times, sender names, subjects); no
  email bodies. The API key stays server-side.

## Daily briefing

`services/briefing.py` collects today's context (agenda, due/overdue tasks, pending reminders,
attention emails, current priorities) into a compact JSON document, then:

1. **AI path** (when `ANTHROPIC_API_KEY` is set): one Messages API call to `claude-opus-5-5`
   (`ANTHROPIC_MODEL` overrides) with `output_config.format` = JSON schema and `effort: low`
   (a short summarisation task). The server-side refusal fallback (`fallbacks: "default"`) is
   enabled. The JSON is validated with Pydantic; suggested priorities must reference real task
   ids or be plain text. Refusals, `max_tokens` stops, invalid JSON and API errors are caught.
2. **Rule-based path** (no key, or the AI call failed): deterministic summary — counts, first and
   next meeting, overdue high-priority work first, free blocks between meetings.

Each stored briefing records `source` (`ai` / `rule`) and the model, and the UI labels it. If the
AI call fails, the rule-based briefing is returned with a visible note explaining why. Generation
is rate-limited to one request per user per 30 s to avoid accidental spend.

## Calendar sync

`services/ics.py` parses a feed with `icalendar`, expands occurrences with
`recurring-ical-events` inside a window of 30 days back / 180 days forward, converts to UTC
(floating times use the user's timezone; `DATE` values become all-day events), and replaces the
source's events in one transaction. Errors are stored on the source (`last_error`) and shown in
Settings.

## Email sync

`services/imap.py` connects with `IMAP4_SSL`, `SELECT`s the mailbox read-only, searches
`SINCE <14 days ago>`, fetches `FLAGS` and `BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)]`
for the newest 200 messages, decodes RFC 2047 headers and upserts by UID. Nothing is ever written
back to the mailbox.

## Frontend structure

```text
src/
  api/            client.ts (fetch wrapper, CSRF header, errors), types.ts, hooks.ts (TanStack Query)
  components/     Layout, CommandBar, Toasts, ConfirmDialog, Modal, EmptyState, TaskForm, …
  features/       dashboard/, tasks/, calendar/, inbox/, settings/, auth/
  lib/            quickAdd.ts (natural-language parser), dates.ts
  styles/         tokens.css (light/dark design tokens), app.css
```

## Testing strategy

- **Backend (pytest):** fresh SQLite database per test; covers auth, authorization isolation,
  CSRF, rate limiting, each CRUD router, timezone-aware views, ICS parsing (recurrence, all-day,
  TZID), IMAP mapping with a fake `imaplib` client, encryption round-trip, briefing (rule, AI with
  a fake client, AI failure fallback, invalid AI JSON), and Alembic migrations.
- **Frontend (Vitest):** quick-add parser, API client error handling, key components.
- **End-to-end:** manual run in a browser, recorded with screenshots in `docs/screenshots/`.

## Decisions log

| Decision | Alternatives | Reason |
|---|---|---|
| ICS + IMAP instead of Google/Microsoft OAuth | OAuth APIs | Works with every provider, no app registration or client secrets; OAuth is a documented future step |
| Cookie session + CSRF header | JWT in localStorage | Token never readable by JS; simple revocation |
| On-demand sync | Background scheduler | Keeps the MVP single-process and predictable |
| Rule-based fallback | Disable briefing without a key | The core "daily briefing" feature works for everyone; AI is clearly labelled when used |
