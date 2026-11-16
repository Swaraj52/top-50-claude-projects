# Architecture: Loom (Project 08)

## 1. Shape

```text
Browser ──HTML forms / small HTMX──▶ FastAPI (Jinja2, server-rendered)
                                       ├── routes/auth.py       register · login · logout
                                       ├── routes/library.py    dashboard · library · search · ask
                                       │                        clusters · collections · tags · items
                                       ├── routes/settings.py   profile · password · export · delete
                                       ├── services/search.py   parse · rank · snippet · related
                                       ├── services/clusters.py tag-first topic clusters
                                       ├── services/ask.py      extractive answer + citations
                                       ├── services/ai.py       optional Claude rewrite
                                       └── SQLAlchemy ──▶ SQLite (data/loom.db)
                                                          └──▶ api.anthropic.com (optional, key only)
```

One Python process serves HTML, static files and the health endpoint on port 8008. There is no build
step, no client-side router and no background worker. Every page renders completely on the server;
HTMX is used only for the few in-place actions, and every one of those also works as a normal form
POST.

`app/main.py` is the app factory: settings, engine/sessionmaker, migrations on startup, security
headers, JSON/HTML error handling, static mount and the three routers. `app/web.py` holds the request
context, the session dependency, CSRF helpers and the Jinja2 render function.

## 2. Request lifecycle

1. **Cookie to context.** `web.ctx()` reads the `loom_session` cookie, looks up the SHA-256 hash in
   `sessions`, checks expiry, loads the user and exposes `(user, session, csrf_token)`.
2. **Auth gate.** Pages that need an account depend on `ctx()`; a missing or expired session raises
   `LoginRequired`, which redirects to `/login` (or sends `HX-Redirect` for HTMX requests).
3. **CSRF.** Every state-changing form embeds the session's CSRF token. `web.check_csrf()` compares
   it in constant time; a mismatch renders a `403` page that says the form expired.
4. **Render.** The route loads a `selectinload(Item.collection)` set, filters or ranks in Python,
   and renders a Jinja2 template with the same shell (masthead search, nav, footer credit, AI badge).
5. **Errors.** `HTTPException` and validation errors render the same shell with a status and a plain
   message; HTMX requests receive `HX-Reswap: none` plus an `app-error` trigger instead of a page.

## 3. Data model

| Table | Columns | Notes |
|---|---|---|
| `users` | `id`, `email` (unique), `name`, `password_hash`, `timezone`, `created_at` | Email stored lowercase; password hashed with `scrypt` |
| `sessions` | `id`, `user_id` → users (CASCADE), `token_hash` (unique), `csrf_token`, `created_at`, `expires_at` | The cookie holds the raw token; only its SHA-256 hash is stored |
| `collections` | `id`, `user_id` → users (CASCADE), `name`, `description`, `created_at` | `UNIQUE(user_id, name)`; name clamped to 60, description to 240 |
| `items` | `id`, `user_id` → users (CASCADE), `collection_id` → collections (SET NULL), `title`, `body`, `kind`, `origin`, `source_url`, `author`, `tags`, `starred`, `created_at`, `updated_at` | Kinds: note, article, reference, snippet. Origins: written, uploaded, imported, bookmark |

Indexes: `(user_id, updated_at)`, `(user_id, kind)` and `collection_id` on `items`. Check constraints
limit `kind` and `origin` to the documented sets. Tags are stored as one comma/semicolon-separated
string, cleaned through `split_tags()` on the way in (32 characters each, ten maximum, case-insensitive
deduplication, original casing kept for display).

Alembic migration `0001_initial_schema.py` creates everything; the app upgrades to `head` on startup
unless `RUN_MIGRATIONS=false`.

## 4. Query understanding and ranking

`parse_query()` is the only place a raw string becomes a query. It:

1. Normalises Unicode (curly quotes and dashes become ASCII), collapses whitespace and trims.
2. Extracts `kind:`, `tag:`, `in:`/`collection:` and `is:` filters. A `kind:` not in `KINDS` or an
   `is:` other than starred is recorded in `ignored` and shown in the UI.
3. Extracts quoted phrases and lowercases them.
4. Tokenises the rest, drops stopwords and one-character tokens, and stems with a small suffix
   stemmer (`pricing → pric`, `studies → study`, `boxes → box`).
5. Keeps the first twelve terms, expands each through a fixed symmetric synonym table, and records
   the user's surface form for every term (`surface`, `terms_display`). The interface never prints an
   internal stem.

Ranking is a BM25-flavoured score, not a probability:

- Document frequency is counted over the filtered pool for every query term and expansion.
- Weighted term frequency uses field weights: title 3.0, tags 2.2, author 1.4, source host 1.2,
  body 1.0, saturated as `tf / (tf + 1.2)`.
- IDF is `log(1 + (N - df + 0.5) / (df + 0.5))`.
- Original terms count fully; synonym expansions count at 0.55.
- A quoted phrase adds `6.0 × (2 × title hits + body hits)`.
- If every original term is present, a flat `+3.0` bonus applies; a starred filter adds `+1.0`.
- With terms or phrases active, an item with no positive score is dropped.
- `Hit.percent` is `round(100 × score / (score + 6))`, bounded to 1–100 for display only.

Ties break by most recently updated, then id. The default result limit is 40.

Filters compare collections and tags by slug (`Client Work` equals `client-work`), and a collection
filter is a substring match on the slug, so `in:client` finds `Client work`. Unknown library filters
are ignored rather than erroring, and the library page prints what it actually applied.

## 5. Snippets and related items

`snippet(body, terms, width)` finds the earliest match, takes a window around it, trims to word
boundaries, HTML-escapes everything, then wraps matches in `<mark>`. The term list passed in is
always display forms, so the highlight matches what the user typed. If nothing matches, it returns a
truncated, escaped opening; an empty body returns an empty string. Markup in the body cannot inject
HTML because escaping happens before the only trusted tags are added.

`related(items, target)` compares the target's token set with every other item owned by the same
user, keeps shared terms that are not numbers and not in `RELATED_NOISE`, scores them with the same
IDF, and returns the top four with display-form `matched` lists and a snippet. This powers "Nearby
in the library" on the item page without a separate index.

## 6. Clusters

`build_clusters(items, limit=6, min_shared=2)` runs on every request and stores nothing.

1. For each item, collect tag terms (stemmed) and title terms (stemmed). Body text is deliberately
   excluded: a cluster should be a subject the user named, not a word that happened to repeat.
2. Count document frequency across tags and titles, plus a weighted frequency (tag 2, title 3).
3. A candidate must appear in at least two items, be longer than two characters, not be numeric, and
   not be in `GENERIC` (a documented list of function words and filler such as `first`, `note`,
   `keep`, `return`, `time`).
4. The upper bound is all items when the library has fewer than five items; otherwise a term shared
   by more than 60% of the library is treated as background, not a subject.
5. Candidates sort tag-first (a tag shared by at least two items before any title word), then by
   document frequency, weighted frequency and alphabetically.
6. Members are all items containing the term, newest first. Clusters may overlap. A member set that
   already produced a cluster is skipped, so two names never describe exactly the same set.
7. A display name joins the term with up to two other terms shared by every member, using
   `label()` and title case (`Database · Performance`). The slug is derived from the display name,
   so `/clusters/database-performance` is stable and readable.

Cluster detail resolves a slug by rebuilding the clusters and matching it; an unknown slug is a
`404` rendered in the normal shell. The page says plainly that clusters are recomputed and that
there is no hidden model.

## 7. Ask: retrieve, quote, optionally rewrite

`ask.compose(question, query, hits)` is deterministic and always available.

1. Parse the question with the same `parse_query()`; the UI shows every term, expansion, phrase and
   filter under "How the question was read".
2. `search()` returns up to eight items using the normal ranking.
3. For up to three distinct items, choose `best_sentence(body, terms)`: split on sentence punctuation,
   prefer the sentence with the most distinct query terms, break ties by earlier position, clamp to a
   readable length and fall back to the opening sentence.
4. Build an `Answer` with `source="local"`, the quoted citations, the count read and a plain note. If
   no item matched, the answer says so and reads zero passages.
5. Only then, if `ANTHROPIC_API_KEY` is set and the local answer has citations, `ai.upgrade()` sends
   the question plus at most four passages (trimmed to 700 characters each) to the Messages API with
   a system instruction to use only those passages and return strict JSON.
6. Claude's answer must be a string of 20–1600 characters after whitespace collapse. On success the
   answer keeps the local citations and is labelled `source="claude"`. On HTTP error, timeout,
   malformed JSON or invalid length, the local answer is returned with `FALLBACK_NOTE`.
7. The AI limiter allows 12 calls per account per 10 minutes. A blocked call never blocks the local
   answer; the page says the rate limit was reached and shows the local result.

Prompts and responses are not logged. The model receives no email address, password, session data or
items outside the selected passages.

## 8. Route contracts

All HTML routes return `200` on success. Form posts redirect with `303` (POST/redirect/GET) or render
a `4xx` page with the same shell on validation failure. There is no JSON API besides `/health`.

| Method | Path | Contract |
|---|---|---|
| GET | `/` | Dashboard: counts, top four clusters, recent, starred, collections, top tags |
| GET/POST | `/register`, `/login`; POST `/logout` | Session creation and removal; validation errors keep the form values |
| GET | `/library` | `kind`, `tag`, `collection` (id), `starred`, `sort` (`recent`, `oldest`, `title`); invalid values are dropped |
| GET | `/search` | `q`; renders understanding, hits, snippets or an empty state |
| GET/POST | `/ask` | GET explains the pipeline; POST needs CSRF and a meaningful question |
| GET | `/clusters`, `/clusters/{slug}` | Recomputed clusters; unknown slug is `404` |
| GET/POST | `/collections` | List with counts; create with name/description |
| POST | `/collections/{id}`, `/collections/{id}/delete` | Rename or delete; deleting unsets `collection_id` on items |
| GET | `/tags` | Tag counts, case-insensitive |
| GET/POST | `/items/new` | Create; `kind` query preselects a kind; validation re-renders with a message |
| GET | `/items/{id}` | Detail, related items, star, edit/delete |
| GET/POST | `/items/{id}/edit` | Update title/body/kind/tags/author/URL/collection/star |
| POST | `/items/{id}/star` | Toggle; `next` must be a same-site path or the detail page is used |
| POST | `/items/{id}/delete` | Delete and redirect to the library |
| POST | `/items/upload` | Multipart file; redirects to the edit form, or to `/items/new?upload=type\|large\|missing` |
| GET/POST | `/settings` | Profile and timezone; `?saved=1` shows confirmation |
| POST | `/settings/password` | Current + new password; ends other sessions |
| GET | `/settings/export` | `application/json`, attachment `loom-export.json` |
| POST | `/settings/delete` | Password + typed `DELETE`; deletes the user and cascades |

## 9. Export and import

The export is an object with `format: "loom-export-v1"`, `exported_at`, `exported_for` (the account
email), `collections` (`name`, `description`) and `items` (title, body, kind, origin, tags as a list,
collection name, source URL, author, starred, created/updated ISO timestamps in UTC). It contains no
credentials: a test asserts that `password`, `token`, `csrf`, `api_key` and `hash` do not appear in
the serialized payload.

`scripts/import_data.py` reads that file:

- Requires `--email` for an existing account, and offers `--dry-run`.
- Rejects a file without an `items` list or with an unknown `format`.
- Collapses one-line fields, clamps lengths, keeps at most 100,000 body characters, accepts only
  `http(s)` URLs, coerces flags and parses ISO timestamps with `Z` or an offset.
- Creates missing collections by case-insensitive name and reuses existing ones.
- Skips an item when the same account already has the same title and the same first 250 body
  characters, which makes a second import a no-op (verified live: 14 imported, then 14 skipped).
- Rolls back on `--dry-run`.

## 10. Security

- **Passwords** use `scrypt` with a per-password salt; verification is constant-time.
- **Sessions** are server-side rows. The cookie is `HttpOnly`, `SameSite=Lax`, `Path=/`, optionally
  `Secure`, and never contains user data. Logout deletes the row; changing the password deletes every
  other row for that user.
- **CSRF** is a per-session random token, compared in constant time on every POST, including login,
  registration and uploads.
- **XSS** is prevented at the template boundary: autoescaping is on, snippets escape before adding
  `<mark>`, and the CSP forbids inline script and external origins (`default-src 'self'`).
- **Uploads** are size-checked before decoding, type-checked by extension and content type, decoded as
  UTF-8 with a BOM tolerance, and reduced to text for HTML. Nothing is executed, and no URL is
  fetched.
- **Ownership** is part of every query: items, collections, exports, cluster members and related
  items are filtered by `user_id`. Guessed ids return `404`; assigning another user's collection id
  is ignored.
- **Rate limits** are in-process sliding windows: login 10 failures / 15 minutes per email+IP, AI 12
  calls / 10 minutes per user. They are a personal-scale safeguard, not a distributed quota.
- **Redirects** from the star action accept only same-site paths.
- **Secrets** live in `PROJECT_08/.env` (git-ignored). `.env.example` contains empty values.

## 11. Time

`UTCDateTime` stores naive UTC and returns aware UTC datetimes. `utcnow()` is the single source of
"now". Templates render relative ages ("3 days ago") and absolute dates use the account's IANA
timezone. Imported timestamps are normalised to UTC; an invalid or missing timestamp falls back to
the import moment.

## 12. Testing strategy

- A session-scoped fixture runs Alembic once into a template database; every test copies that file,
  so tests are isolated and fast without re-running migrations 181 times.
- `Browser` wraps `TestClient`, follows no redirects by default and carries the CSRF token from the
  last rendered page, the way a real form does. `add_item()` and `add_collection()` submit the real
  forms.
- Service tests construct `Item` objects directly for ranking, clustering and sentence selection, so
  scoring edge cases do not need a database.
- Claude tests patch `httpx.post` with a fake transport. They assert the request shape (URL, headers,
  model, prompt bounds), the accepted fenced-JSON form, every fallback path and the visible labels.
  No network call and no real key are used.
- Browser-level smoke tests are run manually against the live preview with Playwright: every page
  returns `200`, no console or page errors, search highlights, and Ask returns a local answer with
  citations.

## 13. Deliberate omissions

- No embeddings or vector store. The lexical engine is inspectable and the synonym table is small;
  meaning-based recall is future work, not a hidden dependency.
- No crawler, page fetch, favicon or title extraction. A saved link is metadata plus the user's text.
- No PDF/DOCX/OCR ingestion. Text files only.
- No public JSON API, no interactive docs, no webhooks.
- No email, calendar or notification delivery.
- No multi-user sharing or roles. Every row belongs to exactly one account.
- No background jobs. Clusters, related items and answers are computed inside the request, which is
  appropriate for a personal library and keeps every result current.
