# Your data for Quorum

What the app keeps, the exact shape of an export, how to bring a previous archive back in, and what
stays on your machine.

## Short version

- Nothing outside your own computer is required. The archive is a single SQLite file.
- Create your own account in the running app, then import by email address. You never need to share
  a password.
- An API key is optional. Without one, extraction is a labelled local rule-based pass.
- **Export → Download JSON** gives you every meeting, decision and follow-up, minus secrets.
- Deleting the account removes the meetings, decisions, follow-ups and sessions in one transaction.

## Safe to share in chat

If you want help putting your own meetings into Quorum, these are not secrets:

| What | Example |
|---|---|
| Meeting title | "Weekly product sync" |
| Meeting date | 2026-11-12 |
| Attendees | "Priya, Arjun, Meera" |
| A decision | "Ship the beta to Lumen on Monday" |
| A follow-up | owner `Priya`, title `send the onboarding deck`, due 2026-11-20 |
| A short, invented set of notes | the sample text used in the README |

Do **not** send your account password, a session cookie, an API key, or a database file that
contains other people's conversations. If you paste real notes into a chat, redact names and
commercial details first.

## The JSON shape

The easiest source is **Settings → Download JSON** in the app. The file is named
`quorum-export.json` and looks like this:

```json
{
  "format": "quorum-export-v1",
  "exported_for": "you@example.com",
  "meetings": [
    {
      "title": "Weekly product sync",
      "occurred_on": "2026-11-12",
      "attendees": "Priya, Arjun, Meera",
      "summary": "The beta goes to Lumen on Monday. Export format is the open question.",
      "notes": "Attendees: Priya, Arjun, Meera\n\nDecisions:\n- Ship the beta to Lumen on Monday\n\nAction items:\n- @Priya send the onboarding deck by Friday\n- Arjun will prepare the export sample next week",
      "source": "local",
      "decisions": [
        {"text": "Ship the beta to Lumen on Monday", "status": "agreed"}
      ],
      "actions": [
        {"title": "send the onboarding deck", "owner": "Priya", "due_date": "2026-11-20", "status": "open"},
        {"title": "prepare the export sample", "owner": "Arjun", "due_date": null, "status": "done"}
      ]
    }
  ]
}
```

A hand-written file with the same `meetings` list works too. `format` and `exported_for` are
informational; the importer only requires `meetings`.

### Field rules

| Field | Rule |
|---|---|
| `title` | Required, trimmed, 3–160 characters. A meeting is matched by title **and** date |
| `occurred_on` | Required ISO date (`YYYY-MM-DD`). Records without a usable date are skipped |
| `attendees` | Optional display string, clamped to 600 characters. `@mentions` are merged in by the extractor |
| `notes` | Optional, clamped to 60,000 characters. Kept verbatim as the source of record |
| `summary` | Optional, clamped to 800 characters. When empty, the local extractor writes one from `notes` |
| `source` | `local` or `claude`; anything else becomes `local`. `model` is only kept for `claude` |
| `decisions[].text` | 3–450 characters. Fewer than 3 characters is dropped |
| `decisions[].status` | `agreed` or `revisit`; anything else becomes `agreed` |
| `actions[].title` | 3–280 characters. Fewer than 3 characters is dropped |
| `actions[].owner` | Optional, clamped to 80 characters. An empty owner stays empty |
| `actions[].due_date` | Optional ISO date, or `null` |
| `actions[].status` | `open` or `done`; anything else becomes `open`. A `done` row gets a completion timestamp |

If a meeting has `notes` but no `decisions` or `actions`, the importer runs the app's own local
extractor and fills them from the notes. That keeps an old plain-text archive useful without
inventing anything.

Importing is **idempotent by design**: an existing `(title, occurred_on)` pair is skipped, so
running the same export twice does not duplicate a meeting or its children.

## Loading it

Create your account in the running app first (Register), then:

```powershell
cd PROJECT_06\backend

# See the counts without writing anything
.\.venv\Scripts\python.exe -m scripts.import_data --email you@example.com mydata.json --dry-run

# Import for real
.\.venv\Scripts\python.exe -m scripts.import_data --email you@example.com mydata.json
```

The importer prints how many meetings, decisions and follow-ups it wrote, and how many records it
skipped. It writes to whatever `DATABASE_URL` points at, so run it against your real database — not
the demo one. If the app is running, importing alongside it is safe; SQLite serialises the writes.

## Where the data lives

| File | Purpose |
|---|---|
| `PROJECT_06/data/quorum.db` | Your real account, meetings, decisions and follow-ups |
| `PROJECT_06/data/demo.db` | Disposable demo archive used by `scripts/preview.py` |
| `PROJECT_06/.env` | Optional local configuration; never committed |

All three are git-ignored. To back up, stop the app and copy `quorum.db` (plus its `-wal` / `-shm`
files if present). To start over, stop the app and delete `quorum.db`; the next start migrates a
fresh database.

## What leaves the machine

By default, **nothing**. The local extractor runs in-process.

If you set `ANTHROPIC_API_KEY` and capture or re-read a meeting, the request to the Anthropic
Messages API contains only:

- the meeting title, date and attendee names;
- the notes, truncated to 12,000 characters.

It does **not** contain your name, email, password, session token, other meetings, decisions or
follow-ups. The response is parsed as JSON, validated and clamped before anything is stored. A
network error, timeout, non-200 response or malformed result stores the local extraction instead and
records a visible note saying the local extractor was used. The UI never claims Claude was used when
it was not.

## Deleting your data

Settings → **Delete account** requires your password and the word `DELETE`. It deletes the user row;
meetings, decisions, follow-ups and sessions are removed by `ON DELETE CASCADE` in a single
transaction. Exports you already downloaded are yours to delete separately.

## Demo data is labelled

`scripts/seed_demo.py` creates `demo@quorum.example` with six meetings and a password documented at
the top of that script. The six meetings are generated by running the real local extractor over
realistic invented notes, so the counts, groups and decision log in the screenshots are real
computations. It is sample data for screenshots and first-run exploration, not anyone's real
conversation. Re-running it wipes and recreates only that demo account.
