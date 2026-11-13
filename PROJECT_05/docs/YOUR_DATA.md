# Your data for Cadence

What the app needs from you to be useful, how to bring existing data in, and what stays private.

## Short version

- Nothing outside your own computer is required. The database is a single SQLite file.
- You never need to share your password. Create the account yourself in the app, then import
  data by email address.
- An API key is optional. Without one, the coach is a labelled local planner.
- Export gives you everything the app stores about your habits and reflections, minus secrets.

## Safe to share in chat

If you want help filling Cadence with your own routines, send any of these; they are not secrets:

| What | Example |
|---|---|
| Habit title | "Morning walk" |
| Why it matters (one or two sentences) | "I want to be someone who walks before the day starts." |
| Cue | "After brushing my teeth" |
| Scheduled weekdays (0 = Monday … 6 = Sunday) | `0,2,4` for Mon/Wed/Fri |
| A day's status | 2026-11-12, done |
| A weekly reflection | Week of 2026-11-09, mood 4, "The walk held", "Late meetings", "Move strength to Tuesday" |

Do **not** send your account password, a session cookie, an API key, or a database file containing
other people's data.

## The JSON shape

The easiest source is **Settings → Download JSON** in the app. The file is named
`cadence-export.json` and looks like this:

```json
{
  "format": "cadence-export-v1",
  "exported_for": "you@example.com",
  "habits": [
    {
      "title": "Read 20 minutes",
      "intention": "I want to think in longer sentences than a feed allows.",
      "cue": "After I put the kettle on",
      "days": "0,1,2,3,4,5,6",
      "status": "active",
      "created_at": "2026-09-18",
      "logs": [
        {"day": "2026-11-12", "status": "done", "note": ""},
        {"day": "2026-11-11", "status": "skipped", "note": "Planned rest"}
      ]
    }
  ],
  "reflections": [
    {
      "week_start": "2026-11-02",
      "mood": 4,
      "worked": "Reading after the kettle is automatic now.",
      "friction": "Strength keeps losing to Wednesday meetings.",
      "change": "Move strength to Tuesday for one week."
    }
  ]
}
```

A hand-written file with the same top-level `habits` list works too. You do not need `format` or
`exported_for` for the importer, only `habits`.

### Field rules

| Field | Rule |
|---|---|
| `title` | Required, trimmed, maximum 120 characters. Habits are matched by title |
| `intention`, `cue` | Optional text; cue is clamped to 160 characters |
| `days` | Comma-separated ISO weekdays. `0` = Monday, `6` = Sunday. Empty or invalid becomes every day |
| `status` | `active`, `paused` or `archived`; anything else becomes `active` |
| `created_at` | Optional date shown as the habit's start; import uses today if omitted |
| `logs[].day` | ISO date. Future dates are skipped |
| `logs[].status` | `done` or `skipped`. Anything else is treated as `done` |
| `logs[].note` | Optional, up to 300 characters (the UI does not edit notes yet) |
| `reflections[].week_start` | Any date in the week; it is normalised to that week's Monday |
| `reflections[].mood` | 1–5, clamped |
| `worked`, `friction`, `change` | Optional text, up to 2000 characters each |

Importing is **idempotent by design**: an existing habit with the same title is skipped, an
existing log for that habit/day is skipped, and an existing reflection for that user/week is
skipped. Running the same file twice does not duplicate anything.

## Loading it

Create your account in the running app first (Register), then:

```powershell
cd PROJECT_05\backend

# Check what would happen without writing anything
.\.venv\Scripts\python.exe -m scripts.import_data --email you@example.com mydata.json --dry-run

# Import
.\.venv\Scripts\python.exe -m scripts.import_data --email you@example.com mydata.json
```

The importer prints counts for habits, logs, reflections and skipped records. It writes to whatever
`DATABASE_URL` points at, so run it against your real database, not the demo one. If the app is
running, it is safe to import alongside it; SQLite serialises the writes.

## Where the data lives

| File | Purpose |
|---|---|
| `PROJECT_05/data/cadence.db` | Your real account and data |
| `PROJECT_05/data/demo.db` | Disposable demo account used by `scripts/preview.py` |
| `PROJECT_05/.env` | Optional local configuration; never committed |

All three are git-ignored. To back up, stop the app and copy `cadence.db` (and its `-wal` / `-shm`
files if present). To start over, stop the app and delete `cadence.db`; the next start migrates a
fresh database.

## What the coach receives

When `ANTHROPIC_API_KEY` is set and you press **Suggest a smaller ask**, the request contains:

- habit title, intention, cue, scheduled weekdays, status and creation date;
- computed statistics (streak, rates) and the most recent 21 log entries.

It does **not** contain your name, email, password, session token, other habits or reflections.
Without a key, nothing leaves the machine; the local coach uses the same inputs in-process.

## Demo data is labelled

`scripts/seed_demo.py` creates `demo@cadence.example` with eight weeks of generated history and a
password documented at the top of that script. It is sample data for screenshots and first-run
exploration, not anyone's real routine. Re-running it wipes and recreates only that demo account.
