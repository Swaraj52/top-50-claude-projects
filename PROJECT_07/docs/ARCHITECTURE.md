# Architecture: Switchboard (Project 07)

How the app is put together, why the boundary sits where it does, and the contracts the code keeps.

## 1. Shape

```text
Browser
  │  HTML forms, links, a little HTMX
  ▼
FastAPI + Jinja2                     app/main.py, app/web.py
  ├── routes/auth.py                 register · login · logout
  ├── routes/mail.py                 dashboard · inbox · compose · thread · drafts · follow-ups
  └── routes/settings.py             profile · mailboxes · password · export · delete
        │
        ├── services/mail.py         .eml parsing · classification · priority · summary · draft
        ├── services/ai.py           optional Claude call, validation, labelled fallback
        └── SQLAlchemy 2.0 ──▶ SQLite
                                  └──▶ Anthropic Messages API (optional, no key by default)
```

One Python process serves the UI on port 8007. Templates are rendered on the server; there is no
JavaScript build, no CDN and no client-side state beyond a toast and a clipboard helper.

**The transport boundary is deliberate.** Nothing in the codebase opens an IMAP socket, starts an
OAuth flow or talks SMTP. Mail enters through three explicit functions in the UI: pasted fields, a
`.eml` upload, or the JSON importer. A message marked "sent" becomes a local `Message` row with
`direction="out"`; no network request leaves the machine.

## 2. Request lifecycle

1. `security_headers` middleware adds CSP, `X-Content-Type-Options: nosniff` and
   `Referrer-Policy: same-origin` to every response.
2. `get_db` opens a SQLAlchemy session per request and closes it in `finally`.
3. `optional_ctx` resolves the `sb_session` cookie: it hashes the token, loads the matching `Session`,
   rejects it when expired, and builds a `Ctx` with the user, timezone, local date and current time.
4. `ctx` raises `LoginRequired` when there is no session. The handler returns `303 /login`, or
   `401 + HX-Redirect: /login` for HTMX requests.
5. Mutating routes depend on `csrf`, which compares the form field (or `X-CSRF-Token`) with the
   session's stored token using `hmac.compare_digest`.
6. `render` injects the common context (`user`, `csrf_token`, `today`, `tz`, `now`, `ai_enabled`,
   `ai_model`, `path`) and returns a Jinja response with an optional status code.

Login and register use a **pre-session CSRF cookie** (`sb_csrf`) because there is no session row yet.
The cookie is set on the GET and compared on the POST.

## 3. Data model

All timestamps are stored naive in UTC through `UTCDateTime` and handed back timezone-aware. All
dates (follow-up due dates) are calendar `Date` values.

```text
users 1───n sessions
  │
  ├──1───n mailboxes 1───n threads 1───n messages
  │                              ├──n drafts
  │                              └──n followups
  └──────────────────────────────── (user_id on every child, ON DELETE CASCADE)
```

| Table | Columns that matter | Constraints |
|---|---|---|
| `users` | `email` unique, `name`, `password_hash`, `timezone`, `signature`, `vips` (text) | `email` unique |
| `sessions` | `token_hash` unique, `csrf_token`, `expires_at` | `user_id` indexed, cascade |
| `mailboxes` | `name`, `address` | `(user_id, address)` unique, cascade |
| `threads` | `subject`, `subject_key`, `participants`, `category`, `category_source`, `status`, `unread`, `starred`, `summary`, `summary_source`, `last_activity_at` | checks on category/status; indexes on `(user_id, last_activity_at)` and `(user_id, category)` |
| `messages` | `direction`, `sender`, `recipients`, `body`, `received_at`, `external_id` | direction check; `(user_id, external_id)` unique; thread index |
| `drafts` | `subject`, `body`, `tone`, `source`, `status`, `note` | checks on status/source; thread and `(user_id, status)` indexes |
| `followups` | `title`, `due_date`, `status`, `completed_at` | status check; `(user_id, status, due_date)` and thread indexes |

`subject_key` is the cleaned subject used for threading; the display `subject` keeps the user's
original capitalisation.

### Why the access token is hashed

The session cookie carries a random token. The database stores only its SHA-256 hash, so a leaked
database file does not hand over live sessions. Sessions expire after `SESSION_DAYS` (30 by default)
and are deleted when the account is deleted.

## 4. Intake and threading

`_ingest(db, c, mailbox, ...)` is the single write path for inbound mail, shared by paste and upload.

1. `clean_text` collapses whitespace and clamps the sender to 254, subject to 200 and body to 60,000.
2. An empty subject becomes `(no subject)`; `subject_key` strips `Re:`, `RE:`, `Fwd:`, `Fw:`, `Aw:`,
   `Sv:`, `Re[2]:` repeatedly and lowercases/collapses the rest.
3. When `external_id` is present, an existing message with the same `(user_id, external_id)` is
   returned and no second row is written.
4. An open thread is looked up by `(user_id, mailbox_id, subject_key)`, newest activity first. A
   closed thread is intentionally not reused.
5. The message is inserted, the thread is refreshed and the request commits once. A failed upload
   therefore leaves no half-thread.

`_refresh_thread` recomputes:

- `participants` from senders and recipient names, deduplicated and clamped to 400;
- `category` from the latest inbound message, **unless** `category_source == "you"`;
- `status` (`open` on inbound; `waiting` on outbound unless closed);
- `unread` (`unread or inbound`);
- `summary` and its label from the local summariser;
- `last_activity_at` as the newest message time.

After "mark sent", the draft route calls `_refresh_thread(..., inbound=False)` and then explicitly
sets `status="waiting"`. It also sets `category="waiting"` when the route is still rule-owned, because
the ball is now in the other person's court.

## 5. Classification

`classify(sender, subject, body, vips)` returns `Classification(category, reasons)`.

| Order | Test | Route |
|---:|---|---|
| 1 | `_NEWSLETTER` wording ("unsubscribe", "manage your preferences", "view in your browser", …) | `newsletter` |
| 2 | `_RECEIPT` wording **and** an invoice/receipt/payment word | `receipt` |
| 3 | A `?`, an `_ASK` phrase ("can you", "could you", "please send", …), or a VIP sender | `reply` |
| 4 | Everything else | `fyi` |

A VIP does not override bulk or receipt mail: a person can forward a newsletter. The reasons list is
what the row and the thread page show, so a misroute is auditable rather than mysterious.

## 6. Priority

`priority(thread, vips, now, unread, starred)` returns `(score, reasons)`:

| Signal | Points |
|---|---:|
| Route base: reply / waiting / fyi / newsletter / receipt | 30 / 12 / 8 / 2 / 2 |
| VIP sender on the latest message | 22 |
| Unread | 8 |
| Starred | 15 |
| A question mark in the latest body | 8 |
| A deadline phrase (`today`, `by Friday`, `before EOD`, …) | 12 |
| Arrived under 24 h / 72 h / 7 days ago | 8 / 5 / 2 |

The score is capped at 100. Every contribution appends a reason; the thread page lists them all, and
the inbox row shows the first. Nothing is model-generated.

## 7. Writing: local first, Claude optional

`services/mail.py` owns the deterministic writer.

- `summarise_local(messages)` keeps the first one or two sentences of the latest inbound message after
  removing greeting lines, quoted reply history (`>` blocks, `On … wrote:`), and a signature.
- `draft_local(thread, messages, user, tone)` always returns `{subject, body}`. It uses `Re: <subject>`,
  opens with the sender's first name (or `Dear` for formal), optionally quotes the ask, offers a
  short acknowledgement, appends the user's signature, and never states an amount or a promise.

`services/ai.py` wraps the optional model call:

- the prompt contains the thread subject, participants and at most the last six messages, each
  truncated, with the whole transcript bounded;
- the response must parse as JSON and pass `_validate_summary` (12–800 characters) or
  `_validate_draft` (`Re:` subject, body ≥ 20 characters);
- code fences are tolerated; everything else falls back;
- the return value is `(result, source, note)`, where `source` is `local` or `claude` and `note`
  states plainly when Claude was unavailable or invalid.

The UI never infers the writer: `summary_source` and `draft.source` are stored, and the stamp reads
`Local` or `Claude`.

## 8. Route contracts

All routes are HTML-first. Mutations return `303 See Other`; validation failures re-render the page
with `422`; missing or cross-account rows return `404`; CSRF failure returns `403`.

| Method | Path | Success | Notes |
|---|---|---|---|
| GET | `/` | 200 | Dashboard: six highest-scoring open threads |
| GET | `/inbox?view=&q=&mailbox=` | 200 | Unknown view → `priority`; 120-row cap |
| GET/POST | `/compose` | 200 / 303 | Accepts `multipart/form-data`; `.eml` ≤ 2 MB |
| GET | `/threads/{id}` | 200 | Marks the thread read |
| POST | `/threads/{id}/category` | 303 | Valid category or `422` |
| POST | `/threads/{id}/status` | 303 | `open` / `waiting` / `closed` |
| POST | `/threads/{id}/star` | 303 | Toggles |
| POST | `/threads/{id}/unread` | 303 | Forces unread |
| POST | `/threads/{id}/delete` | 303 → `/inbox` | Deletes children by cascade |
| POST | `/threads/{id}/summarize` | 303 | Rate-limited AI path |
| POST | `/threads/{id}/draft` | 303 | `tone` and `engine` fields |
| POST | `/drafts/{id}` | 303 | `409` when already sent |
| POST | `/drafts/{id}/send` | 303 | `409` on second send; records an outbound message |
| POST | `/drafts/{id}/delete` | 303 | Keeps the thread |
| GET | `/drafts?status=` | 200 | `draft` / `sent` / `all` |
| GET | `/followups?status=` | 200 | Grouped by the user's local date |
| POST | `/threads/{id}/followups` | 303 | Title ≥ 3 characters or `422` |
| POST | `/followups/{id}/toggle` | 303 | Complete / reopen |
| POST | `/followups/{id}/update` | 303 | Title and optional date |
| POST | `/followups/{id}/delete` | 303 | |
| GET/POST | `/settings` | 200 / 303 | Profile and VIPs |
| POST | `/settings/password` | 303 | Ends other sessions |
| POST | `/settings/mailboxes` | 303 | `409` on duplicate address |
| POST | `/settings/mailboxes/{id}/delete` | 303 | `409` when threads exist |
| GET | `/settings/export` | 200 | `switchboard-export.json` |
| POST | `/settings/delete` | 303 | Password + `DELETE` |

`next` parameters pass through `safe_next`, which accepts only a single-slash relative path, so a
tampered form cannot become an open redirect.

## 9. Export and import

`GET /settings/export` writes `switchboard-export-v1`:

```json
{
  "format": "switchboard-export-v1",
  "exported_for": "you@example.com",
  "mailboxes": [{"name": "Personal", "address": "you@example.com"}],
  "threads": [{
    "mailbox": "you@example.com",
    "subject": "Q4 launch checklist",
    "participants": "Priya Raman",
    "category": "reply",
    "status": "open",
    "starred": true,
    "unread": true,
    "summary": "Priya needs the pricing numbers by Friday.",
    "summary_source": "local",
    "last_activity_at": "2026-11-14T06:30:00+00:00",
    "messages": [{"direction": "in", "sender": "…", "recipients": "…", "body": "…", "received_at": "…"}],
    "drafts": [{"subject": "Re: …", "body": "…", "tone": "warm", "status": "draft", "source": "local", "note": "…"}],
    "followups": [{"title": "…", "due_date": "2026-11-20", "status": "open"}]
  }]
}
```

No password hash, session token, CSRF token or API key is included, and a test asserts that.

`scripts/import_data.py` reverses it:

- validates the `format` and the `threads` list;
- resolves the destination account by email;
- creates missing mailboxes;
- clamps every field to the same limits as the app;
- **skips a thread** when the same mailbox, `subject_key` and first-message second already exist, so
  the same file can be imported repeatedly;
- fills a missing summary or route with the local services;
- runs entirely inside one transaction, and `--dry-run` rolls it back.

The verified round trip is 12 threads, 15 messages, 4 drafts and 7 follow-ups; the second and third
imports skip every thread.

## 10. Security

| Concern | Treatment |
|---|---|
| Passwords | `hashlib.scrypt` with a 16-byte random salt, parameters stored in the hash string |
| Sessions | 32-byte URL-safe token in `sb_session`; database stores only SHA-256; 30-day expiry |
| Cookies | `HttpOnly`, `SameSite=Lax`, `Secure` when `COOKIE_SECURE=true` |
| CSRF | Per-session token on every mutation; pre-session cookie for login/register |
| XSS | Jinja autoescaping; message bodies rendered as text, not HTML |
| SQL injection | SQLAlchemy expressions; search uses `ilike(..., escape="\\")` with escaped `%` and `_` |
| Open redirects | `next` accepts only a single-slash internal path |
| Uploads | 2 MB cap; parsed with the standard library; the file itself is discarded |
| Abuse | Login 10 / 15 min; AI 8 / 10 min; per-process sliding window |
| Headers | CSP (`default-src 'self'`), `nosniff`, `same-origin` referrer |
| Isolation | Every lookup filters by `user_id`; cross-account ids are `404` |
| Secrets | `.env` is git-ignored; only `.env.example` is committed |

## 11. Time

- `utcnow()` is the only clock for stored instants.
- `zone(name)` returns a `ZoneInfo`, falling back to UTC for an invalid name.
- `local_today(tz)` decides "today"; `monday_of` anchors the dashboard week.
- `parse_local_datetime` interprets a `datetime-local` value in the user's zone and converts to UTC.
- `relative_day` understands `today`, `tomorrow`, `next week`, weekdays, `by Friday` and ISO dates,
  returning `None` for anything it cannot parse.
- `dt` and `datefmt` template filters format for display only; storage stays UTC.

## 12. Testing strategy

- Each test gets a copy of a session-scoped migrated SQLite file, so tests never share state and
  never touch `data/`.
- `Browser` wraps `TestClient`, carries the CSRF token between GET and POST, and exposes
  `register()`, `login()` and `post()`.
- `compose()` and `make_eml()` build realistic intake without duplicating form fields in every test.
- Claude tests patch `httpx.post` at the module boundary; no key and no network.
- Ownership tests create a second browser and assert `404` on every cross-account route.
- The importer is verified by exporting the demo, importing into a scratch database and importing
  again to prove the skip path.

## 13. Deliberate omissions

- No background worker, queue or scheduler: the app is a request/response desk.
- No attachment storage: `.eml` parts other than the text body are ignored.
- No vector index: SQLite `ilike` over a personal archive is fast and predictable.
- No JSON API: the HTML routes are the product; `/health` is the only machine endpoint.
- No public deployment configuration: the app binds to `127.0.0.1` by default and documents
  `COOKIE_SECURE` for anyone who fronts it with HTTPS.
