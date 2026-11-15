# Your data for Switchboard

What the app keeps, the exact shape of an export, how to bring a previous desk back in, and what
stays on your machine.

## Short version

- Nothing outside your own computer is required. The archive is a single SQLite file.
- There is **no mailbox connection** and no password field for one. Mail arrives by paste, `.eml`
  upload or a Switchboard JSON import.
- Create your own account in the running app, then import by email address. You never share a
  password to import.
- An API key is optional. Without one, summaries and drafts come from the labelled local writer.
- **Settings → Download JSON** gives you every thread, message, draft and follow-up, minus secrets.
- Deleting the account removes all of it in one transaction.

## Safe to share in chat

If you want help putting your own mail into Switchboard, these are not secrets:

| What | Example |
|---|---|
| Thread subject | "Q4 launch checklist" |
| Sender | `Priya Raman <priya@lumen.example>` |
| A message body | "Could you review the pricing section by Friday?" |
| A route | `reply` |
| A draft | "Hi Priya, I will send the numbers today." |
| A follow-up | title `Signed contract from Arjun`, due `2026-11-20` |
| A short, invented sample | the demo data shown in the README |

Do **not** send your account password, a session cookie, an API key, or a database file containing
other people's mail. If you paste a real message into a chat, redact names, addresses and commercial
details first.

## The JSON shape

The easiest source is **Settings → Download JSON** in the app. The file is named
`switchboard-export.json` and looks like this:

```json
{
  "format": "switchboard-export-v1",
  "exported_for": "you@example.com",
  "mailboxes": [
    {"name": "Personal", "address": "you@example.com"},
    {"name": "Work", "address": "you@work.example"}
  ],
  "threads": [
    {
      "mailbox": "you@example.com",
      "subject": "Q4 launch checklist",
      "participants": "Priya Raman",
      "category": "reply",
      "status": "open",
      "starred": true,
      "unread": true,
      "summary": "Priya needs the pricing numbers confirmed by Friday.",
      "summary_source": "local",
      "last_activity_at": "2026-11-14T06:30:00+00:00",
      "messages": [
        {
          "direction": "in",
          "sender": "Priya Raman <priya@lumen.example>",
          "recipients": "you@example.com",
          "body": "Hi Swayam,\n\nCould you review the pricing section by Friday?\n\nPriya",
          "received_at": "2026-11-14T06:30:00+00:00"
        }
      ],
      "drafts": [
        {
          "subject": "Re: Q4 launch checklist",
          "body": "Hi Priya,\n\nI will confirm the numbers by Friday.\n\nSwayam",
          "tone": "warm",
          "status": "draft",
          "source": "local",
          "note": "Local template evaluated from the latest message; no model call."
        }
      ],
      "followups": [
        {"title": "Confirm the pricing numbers", "due_date": "2026-11-20", "status": "open"}
      ]
    }
  ]
}
```

A hand-written file with the same `threads` list works too. `format` and `exported_for` are
informational; the importer only requires `threads`.

### Field rules

| Field | Rule |
|---|---|
| `mailbox` | Address used to group threads. A missing mailbox is created with the name from the top-level `mailboxes` list, or `Imported` |
| `subject` | Trimmed, max 200 characters. Empty becomes `(no subject)` |
| `messages[]` | A thread with no valid message (missing `received_at` or empty body) is skipped |
| `messages[].direction` | `in` or `out`; anything else becomes `in` |
| `messages[].sender` | Max 254 characters. Empty becomes `(unknown sender)` |
| `messages[].recipients` | Max 400 characters |
| `messages[].body` | Max 60,000 characters |
| `messages[].received_at` | Required ISO 8601 timestamp with an offset or `Z`; naive values are treated as UTC |
| `category` | `reply`, `waiting`, `fyi`, `newsletter` or `receipt`. Anything else is recomputed by the local classifier |
| `status` | `open`, `waiting` or `closed`; anything else becomes `open` |
| `starred`, `unread` | Booleans; strings `true/false/yes/no/1/0/on` are accepted |
| `summary` | Max 800 characters. When empty, the local summariser writes one from the latest inbound message |
| `summary_source` | `local` or `claude`; anything else becomes `local` |
| `drafts[].subject` | At least 2 characters, max 200 |
| `drafts[].body` | At least 2 characters, max 60,000 |
| `drafts[].tone` | Max 10 characters, default `warm` |
| `drafts[].status` | `draft` or `sent`; anything else becomes `draft` |
| `drafts[].source` | `local` or `claude`; anything else becomes `local` |
| `followups[].title` | 3–240 characters. Shorter titles are dropped |
| `followups[].due_date` | Optional ISO date (`YYYY-MM-DD`) or `null` |
| `followups[].status` | `open` or `done`; anything else becomes `open`. A `done` row gets a completion timestamp |

## How duplicates are avoided

Importing is **idempotent by design**: a thread is skipped when the same **mailbox**, cleaned
**subject** and **first-message second** are already stored. Running the same export twice therefore
adds nothing. A genuinely new message on the same subject is a different thread only if its first
message differs; otherwise it belongs to the existing thread and should be added through the app.

## Loading it

Create your account in the running app first (Register), then:

```powershell
cd PROJECT_07\backend

# See the counts without writing anything
.\.venv\Scripts\python.exe -m scripts.import_data --email you@example.com switchboard-export.json --dry-run

# Import for real
.\.venv\Scripts\python.exe -m scripts.import_data --email you@example.com switchboard-export.json
```

The importer prints how many threads, messages, drafts and follow-ups it wrote, how many mailboxes
it created, and how many records it skipped. It writes to whatever `DATABASE_URL` points at, so run
it against your real database — not the demo one. If the app is running, importing alongside it is
safe; SQLite serialises the writes.

## Where the data lives

| File | Purpose |
|---|---|
| `PROJECT_07/data/switchboard.db` | Your real account, threads, messages, drafts and follow-ups |
| `PROJECT_07/data/demo.db` | Disposable demo desk used by `scripts/preview.py` |
| `PROJECT_07/.env` | Optional local configuration; never committed |

All three are git-ignored. To back up, stop the app and copy `switchboard.db` (plus its `-wal` /
`-shm` files if present). To start over, stop the app and delete `switchboard.db`; the next start
migrates a fresh database.

## What leaves the machine

By default, **nothing**. Classification, priority, summaries and local drafts all run in-process.

If you set `ANTHROPIC_API_KEY` and ask for a Claude summary or draft, the request to the Anthropic
Messages API contains only:

- the thread subject and participant names;
- the last six messages, each truncated, with the whole transcript bounded;
- for a draft: the chosen tone and your signature.

It does **not** contain your name, email, password, session token, other threads, or the archive.
The response is parsed as JSON, validated and clamped before anything is stored. A network error,
timeout, non-200 response or malformed result stores the local result instead and records a visible
note saying the local writer was used. The UI never claims Claude was used when it was not.

The `.eml` upload is read into memory, parsed, and turned into a message row; the file itself is not
stored or forwarded.

## Deleting your data

Settings → **Delete account** requires your password and the word `DELETE`. It deletes the user row;
mailboxes, threads, messages, drafts, follow-ups and sessions are removed by `ON DELETE CASCADE` in a
single transaction. Exports you already downloaded are yours to delete separately.

A single thread can be deleted from its own page; that removes its messages, drafts and follow-ups.

## Demo data is labelled

`scripts/seed_demo.py` creates `demo@switchboard.example` with twelve threads and a password
documented at the top of that script. The threads are built by running the real classifier, priority
scorer, summariser and draft writer over realistic invented mail, so the routes, scores and summaries
in the screenshots are real computations. It is sample data for screenshots and first-run
exploration, not anyone's real inbox. Re-running it wipes and recreates only that demo account.
