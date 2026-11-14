# Architecture: Meeting Memory Assistant (Project 06), "Quorum"

## Overview

Quorum is one server-rendered Python process. FastAPI handles routing and form parsing, Jinja2
renders HTML, a small vendored HTMX upgrades in-place actions, and SQLAlchemy talks to SQLite. No
Node build, no external database, no required network service.

```text
┌──────────────────────────────── Browser ────────────────────────────────┐
│ HTML forms · HTMX · app.js (toasts, confirmations) · CSS light/dark      │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │ HTTP :8006
┌───────────────────────────────────▼─────────────────────────────────────┐
│ FastAPI app (app/main.py)                                                │
│  middleware: CSP + nosniff + referrer policy                             │
│  error handlers: 404 / 422 / LoginRequired → HTML or HX-Trigger          │
│                                                                          │
│  routes/auth.py      register · login · logout                           │
│  routes/meetings.py  dashboard · archive · capture · detail · edit ·     │
│                      delete · re-extract · actions · decisions · memory  │
│  routes/settings.py  profile · password · export · delete                │
│                                                                          │
│  services/extract.py  deterministic notes → summary/decisions/actions    │
│  services/ai.py       Claude JSON call → validate → labelled fallback    │
│                                                                          │
│  web.py      sessions, CSRF, template filters, auth dependencies         │
│  timeutil.py timezone-aware today, due-date parsing, attendees           │
│  security.py scrypt hashing, token hashing, sliding-window limiter       │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ SQLAlchemy 2
                     ┌──────────▼──────────┐        ┌────────────────────┐
                     │ SQLite              │        │ Anthropic Messages │
                     │ data/quorum.db      │        │ API (optional)     │
                     └─────────────────────┘        └────────────────────┘
```

## Data model

```
users 1───n sessions
  │
  └──1───n meetings 1───n decisions
                 └───n action_items
```

| Table | Columns | Notes |
|---|---|---|
| `users` | `id`, `email` (unique), `name`, `password_hash`, `timezone`, `created_at` | Timezone is an IANA name |
| `sessions` | `id`, `user_id` FK cascade, `token_hash` (unique), `csrf_token`, `created_at`, `expires_at` | Only the SHA-256 of the cookie token is stored |
| `meetings` | `id`, `user_id` FK cascade, `title`, `occurred_on`, `attendees`, `notes`, `summary`, `source`, `model`, `extract_note`, `created_at`, `updated_at` | `source ∈ {local, claude}`; index `(user_id, occurred_on)`; attendees are a comma-separated display string |
| `decisions` | `id`, `user_id` FK, `meeting_id` FK cascade, `text`, `status`, `decided_on`, `created_at` | `status ∈ {agreed, revisit}`; indexes `(user_id, decided_on)` and `(meeting_id)` |
| `action_items` | `id`, `user_id` FK, `meeting_id` FK cascade, `title`, `owner`, `due_date`, `status`, `completed_at`, `created_at` | `status ∈ {open, done}`; index `(user_id, status, due_date)` and `(meeting_id)` |

`UTCDateTime` in `db.py` normalises datetimes to UTC on the way in and out. Meeting and decision
dates are stored as `Date` in the user's local calendar; the timezone is only used to decide what
"today" is for grouping and overdue checks.

Design choices:

- **The meeting is the root.** Decisions and follow-ups are children with `ON DELETE CASCADE`, so
  deleting a meeting cannot leave orphan rows. SQLite foreign keys are enabled on every connection.
- **The source is stored, not inferred.** `source`, `model` and `extract_note` live on the meeting
  row. A page can therefore say "Local extractor" or "Claude" without asking a service again.
- **Original notes are immutable evidence.** `notes` is kept verbatim (length-clamped) alongside the
  derived `summary`; the detail page can always reveal what was actually written.
- **No materialised counters.** Dashboard and archive counts come from the same scoped queries every
  time, so an edit, completion or re-extraction cannot leave a stale badge.
- **Decision dates follow the meeting.** Editing `occurred_on` updates every child decision's
  `decided_on` in the same transaction, so the log never claims a decision was made on a different
  day from the meeting that produced it.

## Extraction (`services/extract.py`)

The local extractor is a deterministic line scanner. It is the default path and the AI fallback.

```
notes + attendees + meeting day
        │
        ├─ normalise line endings, strip bullets
        ├─ detect block headers  (Summary:\n, Decisions:\n, Action items:\n, Attendees:\n)
        ├─ detect inline headers (Summary: text, Decisions: text)
        ├─ route each line by the current section
        │     ├─ attendees → parse_attendees()
        │     ├─ summary   → join prose into one paragraph
        │     ├─ decisions → strip prefix, split mixed paragraphs into sentences
        │     └─ actions   → split owner, strip due phrase, clamp title
        └─ fall back: first prose paragraph → summary; agreement sentences → decisions;
                      action-looking lines outside a section → actions
```

| Function | Responsibility |
|---|---|
| `extract(notes, attendees_raw, meeting_day)` | The public entry point; never raises on ordinary text |
| `_clean` | Remove bullet markers and collapse whitespace |
| `_split_action` / `_owner_and_title` | Pull owner and title apart from `@name`, `Owner:`, `Name will…` and attendee-led lines |
| `_strip_due` | Remove `by Friday`, `tomorrow`, `next week`, ISO dates and return the parsed day |
| `_looks_like_action` | Prefix, mention, owner label or "Name will…" pattern |
| `_looks_like_decision` | Decision prefix or an agreement phrase |
| `_decisions_in` | Extract only agreement clauses from a mixed paragraph |
| `_trim` | Strip separators and clamp to a per-field limit |

Extraction rules that matter:

- **Prefixes are not content.** `Follow-up:` and `TODO:` are stripped only when they are actually
  prefixes. `Follow up with legal` keeps its verb because it has no colon, which prevents the
  "with their security questionnaire" fragment bug.
- **Owners are evidence-based.** An owner comes from an `@mention`, an `Owner:` label, `Name will…`,
  or an attendee name at the start of the line. Otherwise it stays empty.
- **Due dates are small and explicit.** Only ISO dates, weekdays, `today`, `tomorrow`, `next week`,
  `EOD` and `in a week` are parsed; an unknown phrase remains in the title rather than becoming a
  wrong date.
- **The same weekday means next week.** On a Thursday, "by Thursday" is seven days ahead, not today.
- **Deduplication is case- and punctuation-insensitive.** Repeating a decision in a summary and a
  section produces one row.

## AI pipeline (`services/ai.py`)

```
meeting + notes + attendees
        │
        ├─ no API key ──────────────▶ ExtractResult(source="local",
        │                               note="Local extractor: rules only, no model call.")
        │
        └─ key present
              POST https://api.anthropic.com/v1/messages
                   (httpx, configured timeout, max_tokens=1400)
                        │
                        ├─ JSON parse + _validate()
                        │     summary ≤600, decisions ≤8 ×450,
                        │     actions ≤12 ×240, owner ≤80,
                        │     due_date parsed and within ±730 days
                        │        ──▶ source="claude", model=<id>, note=""
                        │
                        └─ network error / non-200 / bad JSON / thin payload
                                   ──▶ local result +
                                       "Claude was unavailable or returned an invalid
                                        result; the local extractor was used."
```

- The prompt contains only the meeting title, date, attendees and notes (notes capped at 12,000
  characters in the request body). The password, email, session token and other meetings are never
  sent.
- The model is told to return JSON only, to avoid inventing owners or dates, and to keep a decision
  distinct from a topic discussed.
- Markdown fences are tolerated before parsing. Every field is whitespace-collapsed and clamped;
  wrong types or a summary shorter than four characters are a hard failure.
- A due date is discarded when it is more than two years from the meeting day, which catches model
  arithmetic errors without rejecting a legitimate future commitment.
- Attendees always come from the local parser, even when Claude supplies the summary and actions, so
  the attendee list cannot be hallucinated.
- Failures never retry in a loop and never surface a stack trace to the user.

## Routes and rendering

- `app/main.py` creates the app, runs Alembic, installs middleware and exception handlers, mounts
  `/static`, and includes three routers. The OpenAPI docs are disabled; the UI is the contract.
- Every page dependency `ctx` loads the user, session, timezone and local `today`. Anonymous visitors
  are redirected to `/login`; HTMX requests receive `HX-Redirect`.
- `optional_ctx` serves the login/register/error pages with the correct chrome.
- Actions use POST + `303 See Other`, then re-render from the database. This survives refreshes and
  keeps the browser's back button sane.
- `next` parameters are checked by `_safe_next`: only paths starting with a single `/` are accepted,
  so `//host`, `https://…` and `/\host` cannot become open redirects.
- HTMX is used for small in-place actions with a non-JS form fallback. `app.js` shows toasts for
  `app-error` events, confirms destructive actions, fills the browser timezone, and keeps only one
  inline editor open.
- Template filters (`datefmt`, `initial`, `attendees`) are registered once in `web.py`.
- The dashboard, archive, detail, follow-up and decision pages all render from the same scoped ORM
  queries; there is no cached HTML layer to invalidate.

## Security

| Concern | Implementation |
|---|---|
| Passwords | `hashlib.scrypt` (N=2¹⁴, r=8, p=1), 16-byte random salt, constant-time compare |
| Sessions | 32-byte URL-safe token in `qm_session`; SHA-256 stored server-side; 30-day expiry; `HttpOnly`, `SameSite=Lax`, optional `Secure` |
| CSRF | Per-session token in a field and `X-CSRF-Token` header for HTMX; checked on every POST |
| Authorization | Every meeting/decision/follow-up query scopes by `user_id`; another account's id returns 404 |
| Login abuse | 10 attempts / 15 min per client |
| Extraction abuse | 6 runs / 10 min per user |
| Redirects | `next` accepts only same-site paths; hostile values fall back to `/actions` |
| Headers | CSP (`default-src 'self'`, no inline script), `nosniff`, `Referrer-Policy: same-origin`, `frame-ancestors 'none'` |
| Input | Explicit length clamps (title 160, notes 60,000, decision 500, action 280, owner 80), timezone validation, date range checks |
| Secrets | `.env` git-ignored; database files git-ignored; no key required to run |
| Output | Jinja2 autoescaping; notes containing `<script>` are shown as text; JSON export contains only user text |

The Claude call is outbound only. There is no webhook, no inbound model callback, and no third-party
script in the page.

## Migrations and operations

- One Alembic revision (`0001_initial_schema`) creates all tables, constraints and indexes.
- Startup calls `command.upgrade(cfg, "head")` unless `RUN_MIGRATIONS=false`. The same path is used
  by tests, the demo seed and the preview server, so no environment drifts.
- SQLite runs in WAL mode with foreign keys enabled (`db.py`). The database file is the only state.
- `scripts/preview.py` sets `DATABASE_URL` to `data/demo.db`, seeds it, then starts Uvicorn on
  `127.0.0.1:8006`. Real data in `quorum.db` is never touched.
- `scripts/seed_demo.py` builds six meetings by running the real extractor over realistic notes,
  then marks a few follow-ups done and one decision Revisit. Running it again deletes and recreates
  only `demo@quorum.example`.
- `scripts/import_data.py` matches a meeting by `(title, occurred_on)`, skips duplicates, fills a
  missing summary from the extractor, and preserves the exported `source` / `model`.
- Backup is a file copy of the SQLite database while the app is stopped (or a `.backup` command).
- Logs go to stdout via `logging`, with the extraction mode printed at startup and no passwords,
  tokens or notes logged.

## Testing

144 pytest tests use a temporary SQLite file per test and FastAPI's `TestClient`. The shared
`Browser` helper keeps cookies, extracts the CSRF token, and posts forms the way the UI does.
Coverage is organised by boundary:

- **extraction and time** (`test_extract.py`, `test_timeutil.py`) for sections, prefixes, owners,
  due phrases, dedupe, clamps, odd input and relative dates;
- **routes** (`test_auth.py`, `test_meetings.py`, `test_actions_decisions.py`,
  `test_memory_settings.py`) for validation, ownership, redirects, exports, destructive actions,
  grouping and search;
- **AI safety** (`test_ai.py`) for schema validation, request shape, code fences, the no-key path
  and forced HTTP/network/timeout/invalid-JSON failures that must produce a labelled local fallback.

The visual layer was verified with real Playwright captures at desktop and mobile widths, including
dark mode. The screenshots in `docs/screenshots/` are outputs of that run.
