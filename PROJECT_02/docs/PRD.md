# PRD: Second Brain / Life Library (Project 02)

## 1. Problem

People save good things to read later (articles, newsletters, YouTube talks, PDFs) across
bookmarks, read-later apps, inboxes and notes. Months later they remember *that* they read
something useful, but not where, and they can't ask questions across it all. Saved content
becomes a graveyard instead of a library.

## 2. Target users

- Knowledge workers, students and researchers who read and watch a lot and want to reuse it.
- Writers and creators who need to find quotes, facts and sources quickly.

## 3. Use cases

1. Save a web article by pasting its link; the readable text is extracted automatically.
2. Save a YouTube video; title, channel and (when available) transcript are captured.
3. Save a newsletter by pasting it or uploading the `.eml` file; save notes or PDFs.
4. Triage new saves in an **inbox**: keep them in the library, archive, or delete.
5. Organise with **tags**; filter the library by tag, type and favourites.
6. **Search** everything by keyword, with highlighted matching passages.
7. Get a **summary** (TL;DR + key points + suggested tags) of any item.
8. **Ask Your Library** a question and get an answer grounded in saved items, with citations.

## 4. MVP scope (this release)

| Area | Feature |
|---|---|
| Accounts | Register / sign in / sign out; every item, tag and question is private to its owner |
| Capture | URL → article text (main-content extraction); YouTube → oEmbed metadata + transcript (best effort); paste text (newsletter/note); upload `.txt .md .html .eml .pdf`; duplicate-URL detection; bookmarklet to save from any page |
| Content inbox | New items land in the inbox; Keep / Archive / Delete; unread count |
| Tags | Add/remove on items, rename/delete globally, counts; filter by tag |
| Search | SQLite FTS5 (BM25 ranking, Porter stemming, prefix matching) over titles, tags and full text, with highlighted snippets |
| Summaries | Claude summary (TL;DR, key points, suggested tags) when `ANTHROPIC_API_KEY` is set; otherwise an extractive summary + keyword tags, labelled as non-AI |
| Ask Your Library | Retrieve the most relevant passages (BM25 over chunks), then Claude answers only from them, citing sources; without a key, the ranked passages are shown instead (labelled) ; question history |
| Reader | Clean reading view of saved text, source link, reading time, summary panel |

## 5. Out of scope (future)

- Browser extension, mobile share sheet, email forwarding address.
- Semantic (embedding) search; highlights/annotations inside the text; spaced repetition.
- Automatic re-fetching of updated pages; full-video speech-to-text when no transcript exists.

## 6. User stories

- *As a reader,* I paste a link and the article's readable text, title and site are saved.
- *As a viewer,* I paste a YouTube link and can later search and ask about what was said.
- *As a subscriber,* I upload a newsletter `.eml` and it is saved with its subject and sender.
- *As a user,* I see new saves in my inbox and move them to my library or archive.
- *As a user,* I tag items and find them by tag, type, favourite or keyword.
- *As a user,* I click **Summarize** and see a short summary, and whether AI wrote it.
- *As a user,* I ask "what did I save about sleep and memory?" and get an answer with links
  to the exact items it came from.

## 7. Key flows

1. **Capture:** Add bar → paste URL / text / file → item saved to inbox → toast with "Open".
2. **Triage:** Inbox → skim card (summary if available) → Keep / Archive / Delete.
3. **Find:** Search box → ranked results with highlighted passages → open reader.
4. **Ask:** Ask page → question (optionally limited to a tag) → answer with numbered
   citations → click a citation to open the item.

## 8. Non-functional requirements

- Local-first: SQLite file, one process, no external services required.
- Server-side fetching is protected against SSRF (only public http(s) hosts, checked on every
  redirect), with timeouts and size limits.
- Saved content is rendered as plain text (no stored HTML executed in the browser).
- Same security baseline as Project 01: scrypt passwords, HttpOnly session cookie, CSRF header.
- AI is optional and always labelled; tests never call paid APIs.

## 9. Success criteria

- Saving a typical article takes one paste and under 5 seconds.
- Search returns ranked, highlighted results in under 200 ms for thousands of items.
- Ask answers cite only items the user actually saved; with no key the passages still help.
