# PRD: Personal Knowledge Search (Project 08), "Loom"

## 1. Problem

A personal library is not a folder tree. It is a set of things half-remembered: a phrase from a
pricing review, a note about an index, a book you meant to revisit. The tools that promise to make
this searchable usually ask for the whole library to be uploaded to a service, then return a ranked
list with no explanation. When the list is wrong, there is nothing to correct.

Loom starts from three constraints:

1. **The text stays local.** No crawler, no page fetching, no third-party index.
2. **Ranking must be explainable.** The matched words, filters, phrase hits and score are visible.
3. **An answer must show its receipts.** Ask quotes from the library and links every citation.

## 2. Target users

- **A solo consultant or freelancer** with years of client notes, decisions and contracts who needs to
  find "what did we agree about pricing" without opening twelve files.
- **A writer or researcher** who keeps excerpts, references and snippets and wants to see which
  subjects recur across them.
- **A privacy-conscious note-taker** who will not upload a personal knowledge base to a hosted
  semantic search product, but still wants better than filename search.
- **A developer learning retrieval** who wants a small, readable implementation of query parsing,
  BM25-style ranking, snippets, clusters and extractive answers.

## 3. Use cases

1. *"Find the note where we decided the Starter plan keeps its price."* Search `pricing review` and
   read the highlighted passage on the first result.
2. *"Show only notes in the Client work collection."* Search `in:client-work kind:note`.
3. *"Find the exact phrase 'annual discount'."* Quote it; only items containing the phrase qualify.
4. *"What is this library about?"* Open Clusters and read the six subjects built from shared tags and
   titles; click one to see its members.
5. *"What did we decide about pricing for January?"* Ask; read the local answer and its three
   citations, then open the quoted item.
6. *"I have a markdown file of meeting notes."* Upload it, review the parsed text in the edit form,
   add tags and a collection, save.
7. *"I saved a link to an article."* Add a reference with the URL and your own summary. Loom will not
   fetch the page, and says so on the detail page.
8. *"Move these notes into a new shelf."* Create a collection, assign items from the edit form, and
   delete the old collection without losing the items.
9. *"Take my library to another machine."* Download the JSON export, create an account there, and run
   the importer twice — the second run imports nothing new.
10. *"Delete everything."* Settings → delete account with the password and a typed `DELETE`.

## 4. MVP scope (implemented)

### Accounts and access

- Register with name, email, password (8+ characters) and an IANA timezone; sign in and out.
- `scrypt` password hashing; server-side sessions stored as a SHA-256 token hash; `HttpOnly`,
  `SameSite=Lax` cookie; CSRF token on every state-changing form.
- Login rate limit (10 failures / 15 minutes per email+IP) and AI rate limit (12 calls / 10 minutes
  per account). Cross-account ids return `404`.

### Library

- Four kinds: note, article, reference, snippet. Optional author, `http(s)` source URL, collection,
  tags (up to ten, deduplicated and clamped) and starred flag.
- Body limit 100,000 characters; title required and clamped to 200.
- Library filters by kind, tag, collection and starred; sort by recently updated, oldest or title.
- Item detail with preserved paragraphs, source host, related items from shared rare terms, star,
  edit and delete. Deleting a collection leaves its items unshelved.

### Writing and upload

- New/edit forms with server-side validation and inline error messages.
- Upload `.md`, `.txt` or `.html` (512 KB cap). UTF-8 BOM tolerated; HTML parsed to text with
  `script` and `style` removed; the item opens in the edit form for review before saving.
- No URL fetching. A saved link is metadata plus the user's own summary.

### Search

- Filler-word removal, light suffix stemming, a fixed symmetric synonym table, quoted phrases.
- Filters: `kind:`, `tag:`, `in:` (collection, compared slug-wise), `is:starred`. Unknown filters are
  listed as ignored rather than silently discarded.
- BM25-style scoring with document-frequency IDF, title 3× / tags 2× / body 1× weights, a phrase
  bonus and an all-terms bonus. Results show matched surface words, phrase count, a bounded
  percentage and a highlighted snippet.
- A "How this was understood" panel lists terms, expansions, phrases, filters and ignored tokens.
- Related items on the detail page use the same IDF idea over shared rare terms, excluding numbers
  and function words.

### Clusters

- Up to six clusters (four on the dashboard) from two or more items.
- Candidates come from tags first, then title words. A documented blacklist removes generic words
  (`first`, `keep`, `note`, `return`, …). Terms shared by more than 60% of a library of five or more
  items are not subjects; smaller libraries may use all items.
- Clusters may overlap; identical member sets are not repeated. Names use display words, never stems.
- Nothing is stored: every page recomputes from the current library.

### Ask

- Natural-language question (500 characters), parsed with the same query understanding.
- Retrieval of up to eight items; one sentence per item selected by term overlap; up to three
  citations with item links and quoted sentences.
- Local extractive answer labelled **Local extract**, with a note explaining that no passage was
  invented and no passage was read when nothing matched.
- Optional Claude rewrite over at most four trimmed passages, strict JSON, 20–1600 characters;
  labelled **Claude**; any failure returns the local answer with a fallback note.
- The page explains the three-step pipeline before the first question and shows "How the question was
  read" after one.

### Settings and data

- Name and timezone (validated against `zoneinfo`), password change that ends other sessions.
- Counts of items, collections, tags and words.
- Full JSON export (`loom-export-v1`) containing collections and items only — no password hashes,
  session tokens, CSRF tokens or API keys.
- Account deletion with password and typed `DELETE`.
- AI status explained in plain words; the app runs with no key.

### UI

- Warm cream paper, deep spruce ink, ochre and rust accents; serif display headings, mono metadata,
  ruled paper texture and card-like results.
- Always-visible masthead search; dashboard, library, search, ask, clusters, collections, tags,
  settings and item pages share the same shell.
- Dark variant via `prefers-color-scheme`; responsive down to 390 px; focus-visible states, toasts,
  empty states and confirmation before destructive actions.
- "Built by **Swayam**" in the footer of every page.

## 5. Out of scope (v1.0)

- Web crawling, URL fetching, reader mode, favicon or title extraction.
- PDF, DOCX, EPUB, image or OCR ingestion.
- Embeddings, a vector database or a hosted semantic index.
- Multi-user sharing, teams, comments or public libraries.
- Mobile apps, a public API, webhooks or browser extensions.
- Email or calendar integration; reminders and notifications.
- Public deployment, paid services or any feature that requires an API key.

## 6. Success criteria

1. A new user can register, add an item, find it by a remembered word, upload a markdown file, and
   ask a question with citations without reading documentation.
2. Search never shows an internal stem in the UI; every result shows matched words and a highlighted
   passage; every active filter is visible in the understanding panel.
3. Clusters contain only subjects, never generic words, and change when items are edited.
4. Ask never invents a citation; with no match it says so; with no key it is labelled local.
5. The export/import round trip is lossless for title, body, kind, tags, starred, source URL, author,
   collection and timestamps, and a second import adds nothing.
6. All 181 automated tests pass from a clean checkout; the preview starts with one command.
7. No secret is committed and no network call is made by the default configuration.

## 7. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Lexical search misses meaning-based matches | Fixed synonym table, stemming, phrases, visible understanding; limitations stated plainly; embeddings listed as future work |
| A stem leaks into the interface | `label()`/`surface` map every indexed term back to the user's word; tests assert display forms and cluster names |
| Clusters become a bag of generic words | Tag-first candidates, a documented blacklist, a frequency ceiling and minimum of two items |
| An extractive answer reads like a summary and misleads | Quoted sentences, visible citations, "read N passages" count and a plain note about what was done |
| Claude returns prose that is not supported by the passages | Strict JSON, length validation, passages only, citations come from local retrieval, labelled fallback |
| HTML upload injects markup | Parse to text with `HTMLParser`, drop `script`/`style`, escape everything rendered; snippets escape before adding `<mark>` |
| Export leaks credentials | Export selects only collection and item fields; a test asserts no password/token/hash keys |
| Cross-account data exposure | Every query filters by `user_id`; guessed ids return `404`; tests cover isolation |
| SQLite and in-process limits | Documented as single-user scale; no multi-worker claim |

## 8. Milestones

| Milestone | Scope | State |
|---|---|---|
| M1 | Schema, auth, sessions, CSRF, app shell, migrations | Done |
| M2 | Items, collections, tags, library filters, uploads | Done |
| M3 | Search parsing, ranking, snippets, related items, UI | Done |
| M4 | Clusters and cluster pages | Done |
| M5 | Ask pipeline, citations, optional Claude, rate limit | Done |
| M6 | Settings, export, importer, demo seed, preview | Done |
| M7 | 181 tests, screenshots, README/PRD/architecture/data docs | Done |
| M8 | Release v1.0: tag, push, programme trackers | Done |

## 9. Open questions for a future version

- Should a saved link offer an *optional*, explicitly confirmed fetch, with the fetched text stored
  as a separate origin so the user can tell it apart from their own summary?
- Is a local embedding index worth the binary size and first-run cost if the lexical baseline stays
  visible for comparison?
- Should "Ask" support follow-up questions over the same retrieved set, and how should that be
  labelled so citations remain unambiguous?
- Would highlights or margin notes on an item be more useful than another kind?
- Should tags be hierarchical, or does a flat vocabulary plus collections stay clearer at personal
  scale?
