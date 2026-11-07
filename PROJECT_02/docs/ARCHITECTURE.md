# Architecture: Second Brain / Life Library (Project 02)

## Overview

```text
 Browser (React SPA "Stacks")          FastAPI (Python 3.11+)                         Storage / external
┌─────────────────────────────┐ /api  ┌──────────────────────────────────────┐       ┌───────────────────┐
│ Inbox · Library · Reader ·  │──────▶│ routers: auth items tags search ask  │──────▶│ SQLite + FTS5     │
│ Search · Ask · Settings     │cookie │ services: fetcher (SSRF-safe)        │       │ data/library.db   │
│ TanStack Query              │◀──────│   extract (trafilatura, eml, pdf)    │       └───────────────────┘
└─────────────────────────────┘       │   youtube (oEmbed + transcript)      │──────▶ Web pages (http/s)
                                      │   indexer (chunks + FTS rows)        │──────▶ YouTube oEmbed
                                      │   summarize / ask (Claude or rules)  │──────▶ Claude API (optional)
                                      └──────────────────────────────────────┘
```

Dev: Vite on **5102** proxies `/api` to Uvicorn on **8002**. Production: the backend serves the
built SPA, so the app is a single process on 8002.

## Data model

```text
users(id, email UNIQUE, name, password_hash, created_at)
sessions(id, user_id, token_hash UNIQUE, created_at, expires_at)
items(id, user_id, kind[article|video|newsletter|note|pdf], status[inbox|library|archived],
      favorite, title, url?, source_name, author, published?, description, content,
      word_count, has_transcript, thumbnail_url?, summary JSON?, created_at, updated_at,
      UNIQUE(user_id, url))
tags(id, user_id, name, UNIQUE(user_id, name));   item_tags(item_id, tag_id)  -- many-to-many
chunks(id, item_id, user_id, position, text)      -- ~1,200-character passages for retrieval
questions(id, user_id, question, answer, source[ai|passages], model?, citations JSON,
          note?, created_at)

items_fts(title, tags, body)   -- FTS5, rowid = items.id, tokenize = 'porter unicode61'
chunks_fts(text)               -- FTS5, rowid = chunks.id
```

FTS tables are created by the Alembic migration (raw SQL) and kept in sync by
`services/indexer.py` whenever an item's text, title or tags change; they are excluded from
autogenerate comparison. Every query filters by `user_id` (FTS hits are joined back to owned rows).

## Capture pipeline

1. **Fetch** (`services/fetcher.py`): http(s) only; the host is resolved and rejected if any
   address is private, loopback, link-local, multicast or reserved; redirects are followed
   manually (max 5) and re-checked; 15 s timeout; 8 MB cap; HTML/text/PDF content types only.
2. **Extract** (`services/extract.py`): `trafilatura` for article text + metadata (title,
   site, author, date, description); `email` stdlib for `.eml` (subject, sender, best text
   part); `pypdf` for PDFs; plain text/Markdown as-is.
3. **YouTube** (`services/youtube.py`): video id parsed from any YouTube URL form; metadata from
   the official oEmbed endpoint; transcript via `youtube-transcript-api` (best effort; if
   YouTube refuses, the item is saved without one and the user can paste it later).
4. **Index** (`services/indexer.py`): paragraphs are packed into ~1,200-character chunks;
   `items_fts` and `chunks_fts` rows are rewritten.

## Search

User input is tokenised to words, stop words dropped, each term quoted and prefix-matched
(`"term"*`), combined with AND (falling back to OR when AND finds nothing). Results are ranked
by `bm25(items_fts, 10.0, 5.0, 1.0)` (title > tags > body) and carry an FTS `snippet()` whose
highlight markers are rendered as `<mark>` by React (no HTML from the database is injected).

## AI features

| Feature | With `ANTHROPIC_API_KEY` | Without |
|---|---|---|
| Summarize | `claude-opus-5-5`, structured JSON `{tldr, key_points[], suggested_tags[]}`, effort `low`; long texts capped at 120,000 characters and the summary says so | Extractive: top-scoring sentences by term frequency + top keywords as tag suggestions, labelled "Extractive summary" |
| Ask Your Library | BM25 retrieves top 8 chunks (optionally within one tag); Claude answers **only** from them as JSON `{answer, cited_sources[], confidence}`; citations are validated against the provided sources | The same ranked passages are returned, labelled "No AI answer, most relevant passages" |

Both calls use the server-side refusal fallback (`fallbacks: "default"`), catch SDK errors
(auth, rate limit, connection, status), treat refusals/truncation/invalid JSON as failures and
fall back to the non-AI result with a visible note. Only the item text / retrieved passages are
sent; nothing is sent without an explicit user action (button / question).

## Security

- Auth, sessions, CSRF header and rate limiting as in Project 01 (scrypt, HttpOnly SameSite=Lax
  cookie, `X-Requested-With: library` on writes, 10 failed logins / 15 min).
- SSRF-safe fetching (above). Uploads limited to 10 MB and to known extensions.
- Content is stored and rendered as text; thumbnails only from `i.ytimg.com`.

## Testing strategy

pytest with fresh migrated SQLite per test: auth & isolation, SSRF guard (private/loopback
hosts and redirect hops), extraction from fixture HTML/EML/PDF, YouTube URL parsing with mocked
oEmbed/transcript, duplicate detection, inbox transitions, tags, FTS search ranking/snippets,
chunking, summarize (AI fake, fallbacks, extractive), Ask (retrieval, AI fake with citation
validation, passages fallback), migrations. Vitest for the client, snippet rendering, add bar,
and Ask page. Manual browser run against real pages.
