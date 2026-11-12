# Your data for Summit

What the app needs from you to be useful, and how each piece gets in.

## Safe to share in chat

Send any of these and they can be loaded with `scripts/import_data.py`:

| What | Example |
|---|---|
| Goal title, category and target date | "Run a half marathon", health, 2027-02-15 |
| Why it matters (one or two sentences) | "I want to still be running when I am sixty." |
| Milestones: title, optional detail, due date and weight (1 = minor, 5 = the main checkpoint) | "Complete a 15 km long run", due 2026-11-30, weight 3 |
| Current weekly actions: title, matching goal, estimate in minutes | "Book a critique with Priya", 20 |
| Check-ins: goal, date, confidence 1–5, one honest sentence | 2026-11-12, 4, "Legs felt heavy but the long run held together." |

The import does **not** need your password or any API key. Create the account yourself in the app
(Register), then point the importer at that account's email.

## The JSON shape

The easiest source is **Settings → Download JSON** in the app. It exports:

```json
{
  "format": "summit-export-v1",
  "exported_for": "you@example.com",
  "goals": [
    {
      "title": "Run a half marathon",
      "description": "Build to 21.1 km with three runs a week, no heroics.",
      "why": "I want to still be running when I am sixty.",
      "category": "health",
      "status": "active",
      "target_date": "2027-02-15",
      "milestones": [
        {"title": "Run 10 km without stopping", "detail": "Slow and steady.", "due_date": "2026-12-01", "weight": 3, "status": "done"},
        {"title": "Complete a 15 km long run", "detail": "", "due_date": "2026-12-20", "weight": 3, "status": "open"}
      ]
    }
  ],
  "actions": [
    {"goal": "Run a half marathon", "title": "Book a sports massage", "estimate_min": 20, "week_start": "2026-11-09", "status": "open", "source": "manual"}
  ],
  "checkins": [
    {"goal": "Run a half marathon", "day": "2026-11-12", "confidence": 4, "note": "Legs felt heavy but the long run held together."}
  ]
}
```

The importer also accepts a hand-written file where each goal has its own `milestones`, `actions`
and `checkins` arrays. Both shapes can be mixed: nested entries take priority, then top-level
entries are matched to goals by title.

Allowed categories: `career`, `health`, `learning`, `finance`, `personal`, `creative`.
Allowed goal statuses: `active`, `achieved`, `paused`, `archived`.
Allowed action statuses: `open`, `done`, `skipped`. Weights and confidence are clamped to 1–5.

## Loading it

1. Start the app and register your account:

   ```bash
   cd PROJECT_04/backend
   uvicorn app.main:create_app --factory --reload --port 8004
   ```

2. Save the JSON as a file, for example `mydata.json`.
3. Check first, then import:

   ```bash
   cd PROJECT_04/backend
   python -m scripts.import_data --email you@example.com mydata.json --dry-run
   python -m scripts.import_data --email you@example.com mydata.json
   ```

`--dry-run` validates and rolls everything back, printing what it would import. The import checks
the whole file before saving; a malformed file saves nothing.

Running it twice is safe for goals: a goal whose title already exists for that account is skipped.
Check-ins are skipped when that goal already has a check-in for the same day. Actions are not
de-duplicated inside a goal, so do not import the same batch twice if you rely on that.

## Never share

- **Your password.** Register in the app; the importer only needs the email address.
- **Your Anthropic API key.** Put it in `PROJECT_04/.env` as `ANTHROPIC_API_KEY=...` if you want
  Claude-written weekly plans. Without it the app uses the clearly labelled local planner.

## Things you add in the app itself

Check-ins, completed actions and the coach's plan are part of the weekly rhythm. You can import
them, but the intended flow is:

- add goals and milestones once,
- add or generate actions each week,
- record a check-in when your confidence changes,
- mark actions done as you finish them.

That keeps the insights honest: they are computed from what you actually did, not from what you
planned at import time.
