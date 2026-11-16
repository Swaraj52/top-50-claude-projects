# Your data for Loom

Loom is a personal library, so the most useful next step is your own material — but only the part
you are comfortable sharing. Nothing here requires a password, a session token or an API key, and
none of those should ever be pasted into a chat.

## Short version

If you want Loom to feel like *your* library, the best input is:

1. **A folder of markdown or text notes** (`.md` / `.txt`), or
2. **A `loom-export-v1` JSON file** from Settings → Download JSON, or
3. **A short list of saved links** with the title and one or two sentences about why each matters.

Any one of these is enough. Ten to thirty items is plenty for a useful demo; more is welcome.

## Safe to share in chat

- Note titles, tags and the text you wrote yourself.
- Collection names and descriptions.
- Public URLs you saved (the address is fine; Loom never fetches it).
- A JSON export **after** checking it contains only items and collections.

**Never share:** your password, a session cookie, a CSRF token, an `ANTHROPIC_API_KEY`, a database
file from a real account, or anything you would not want copied into a conversation.

## The JSON shape

The export is a single object:

```json
{
  "format": "loom-export-v1",
  "exported_at": "2026-11-15T18:40:00+00:00",
  "exported_for": "you@example.com",
  "collections": [
    {"name": "Client work", "description": "The Lumen pilot"}
  ],
  "items": [
    {
      "title": "Q4 pricing review",
      "body": "Decision: the Starter plan keeps its current price until January.\n\nOpen question: ...",
      "kind": "note",
      "origin": "written",
      "tags": ["pricing", "q4", "decisions"],
      "collection": "Client work",
      "source_url": "",
      "author": "",
      "starred": true,
      "created_at": "2026-11-10T09:15:00+00:00",
      "updated_at": "2026-11-14T16:02:00+00:00"
    }
  ]
}
```

### Field rules

| Field | Rule |
|---|---|
| `title` | Required, 1–200 characters. An item without a title is counted as invalid and skipped |
| `body` | Optional, up to 100,000 characters. Line breaks are preserved |
| `kind` | `note`, `article`, `reference` or `snippet`; anything else becomes `note` |
| `origin` | `written`, `uploaded`, `imported` or `bookmark`; anything else becomes `imported` |
| `tags` | A list of strings (a comma-separated string also works); 32 characters each, ten maximum, duplicates removed case-insensitively |
| `collection` | A name, up to 60 characters. Missing collections are created; names are matched case-insensitively |
| `source_url` | Optional, must start with `http://` or `https://`, up to 500 characters. Loom stores it and never requests it |
| `author` | Optional, up to 120 characters |
| `starred` | `true`/`false`; strings `1`, `true`, `yes`, `on` are accepted |
| `created_at`, `updated_at` | ISO 8601 with `Z` or an offset. Invalid values fall back to the import moment |

A minimal item is just `{"title": "..."}`. Everything else has a safe default.

## How duplicates are avoided

An item is skipped when the same account already has the same **title** and the same **first 250
characters of body**. That is deliberately conservative: two genuinely different notes with the same
title and the same opening are indistinguishable to the importer, so the second is treated as a
repeat. Running the same file twice is safe — the second run reports every item as skipped.

Collections are reused by case-insensitive name, so importing the same file into a second account
does not create duplicates within that account.

## Loading it

First create the receiving account in the app (register normally). Then, from the backend folder:

```powershell
cd PROJECT_08\backend

# See the counts without writing anything
.\.venv\Scripts\python.exe -m scripts.import_data --email you@example.com loom-export.json --dry-run

# Import for real
.\.venv\Scripts\python.exe -m scripts.import_data --email you@example.com loom-export.json
```

The importer prints counts for items, collections, skipped entries and invalid entries. It never
prints note bodies.

If you have a folder of markdown instead, the simplest path is the upload form: **New item → Upload**
accepts `.md`, `.txt` and `.html` up to 512 KB, one file at a time, and opens the parsed text in the
edit form so you can add tags and a collection before saving.

## Where the data lives

- Real library: `PROJECT_08/data/loom.db` (SQLite, git-ignored).
- Demo library: `PROJECT_08/data/demo.db`, recreated by the preview script.
- Uploads are not kept as files: the selected text becomes an item body and the original file is
  discarded.
- The app writes nothing outside `PROJECT_08/data/` and its own log output.

## What leaves the machine

By default: **nothing**. Search, clusters, snippets, related items and answers all run in the Python
process.

If you set `ANTHROPIC_API_KEY`, pressing **Ask** sends the question and up to four selected passages
(trimmed) to the Anthropic Messages API. Items are not sent for search or clustering. The answer is
labelled **Claude**; the local answer is labelled **Local extract**. Remove the key to return to
local-only behaviour, and note that the programme's own demo runs without a key.

## Deleting your data

Settings → **Delete account** requires your password and the typed word `DELETE`. It removes the
user row, and cascades to sessions, collections and items. Deleting a collection alone keeps its
items and simply unshelves them. To remove everything including the database file, delete
`PROJECT_08/data/loom.db` while the app is stopped.

## Demo data is labelled

The demo account is `demo@loom.example` / `loom-demo`. Its name is "Swayam", but every note, client,
book and price in it is invented for the demo. Nothing in the screenshots or the seeded database is
the author's real library.

## What would help most

If you want to contribute real material, send any of:

- 10–30 note titles with their tags and a sentence of body each.
- A markdown folder (or a zip) of notes you already own and are happy to have copied into a local
  demo.
- A list of 10 saved links: title, URL, and one line on why you kept it.
- A description of the subjects you actually search for, in your own words — that is the best input
  for tuning the synonym table and the cluster blacklist.
