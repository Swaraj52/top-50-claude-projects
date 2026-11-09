# Your data for Shutdown

What the app needs from you to be useful, and how each piece gets in.

## Safe to share in chat

Send any of these and they can be loaded with `scripts/import_data.py`:

| What | Example |
|---|---|
| Display name | Swayam |
| Timezone | Asia/Kolkata |
| Daily capacity (hours of focused work you can realistically plan) | 6 |
| Tasks you're working on now: title, and optionally area, priority (1 high to 3 low), estimate in minutes, when (today, tomorrow, backlog or a date) and a due date | "Finish lab report", study, 1, 90, today, due 2026-11-14 |
| Current blockers | "Waiting for lab access" |

The same information as JSON (every section optional):

```json
{
  "settings": {"name": "Swayam", "timezone": "Asia/Kolkata", "capacity_hours": 6},
  "tasks": [
    {"title": "Finish lab report", "area": "study", "priority": 1, "estimate_min": 90,
     "when": "today", "due_date": "2026-11-14"},
    {"title": "Read chapter 4", "when": "backlog"}
  ],
  "blockers": [{"text": "Waiting for lab access"}]
}
```

## Never share in chat

- **Your password.** Create your account yourself in the app (Register). The import only needs
  the account's email address.
- **An Anthropic API key**, if you want Claude-written reviews. Put it in `PROJECT_03/.env`
  as `ANTHROPIC_API_KEY=...`. Without it the app uses rule-based reviews.

## Loading it

1. Start the app (`uvicorn app.main:create_app --factory --port 8003` in `PROJECT_03/backend`) and
   register your account.
2. Save the JSON above as a file, for example `mydata.json`.
3. Run:

   ```bash
   cd PROJECT_03/backend
   python -m scripts.import_data --email you@example.com mydata.json
   ```

The import checks everything first and saves nothing if any entry is invalid. Running it twice adds
the tasks twice, so run it once per batch.

## Things you add in the app itself

Work log entries, wins, learnings, daily check-ins and reviews are written day by day in the app.
They aren't imported, because they're about each day as it happens.
