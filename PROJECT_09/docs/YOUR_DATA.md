# Your data for Keystone

Keystone is a planning desk, so the most useful next step is your own ventures — but only the part
you are comfortable sharing. Nothing here requires a password, a session token or an API key, and
none of those should ever be pasted into a chat.

## Short version

If you want Keystone to feel like *your* desk, the best input is:

1. **A `keystone-export-v1` JSON file** from Settings → Download JSON export, or
2. **A short written brief per venture** — name, one-liner, stage, customer, the money model and the
   next three milestones, or
3. **A filled-in canvas in plain text** — nine headings with a sentence or two under each.

Any one of these is enough. One or two real ventures is plenty for a useful demo; more is welcome.

## Safe to share in chat

- Venture names, one-liners, stage, horizon and currency.
- Market, segment, alternatives and differentiation text you wrote yourself.
- Canvas notes, SWOT items and evidence notes.
- Prices, volumes, confidence levels and monthly costs (whole numbers).
- Milestone titles, owners, due dates and success criteria.
- KPI names, units, baselines, targets and readings.
- A JSON export **after** checking it contains only ventures and their child rows.

**Never share:** your password, a session cookie (`ks_session`), a CSRF token, an
`ANTHROPIC_API_KEY`, or a database file from a real account. The importer never asks for any of
these, and neither should anyone helping you.

## The JSON shape

A `keystone-export-v1` document is a small tree. Every field is optional on import; missing values
fall back to the app's defaults.

```json
{
  "format": "keystone-export-v1",
  "exported_for": "you@example.com",
  "ventures": [
    {
      "name": "Sahaj",
      "one_liner": "Scheduling and invoicing for independent solar installers.",
      "stage": "validating",
      "horizon": "90 days",
      "currency": "INR",
      "market": "Residential solar is growing in Tier-2 cities…",
      "segment": "Owner-run solar installers with two to eight technicians",
      "alternatives": "A notebook, a WhatsApp group and a shared spreadsheet.",
      "differentiation": "The job steps follow solar site visits and subsidy paperwork.",
      "narrative": "…the saved memo, if any…",
      "narrative_source": "local",
      "archived": false,
      "canvas": [
        {"block": "problem", "title": "Job books lose money", "detail": "Missed follow-ups", "sort_order": 1}
      ],
      "swot": [
        {"quadrant": "threat", "text": "An incumbent bundles it", "impact": 5, "evidence": "Pricing page"}
      ],
      "streams": [
        {"name": "Studio plan", "model": "subscription", "price": 1499, "unit": "per month",
         "volume": 40, "confidence": "high", "notes": "Paid monthly"}
      ],
      "costs": [
        {"name": "Support", "amount": 18000, "kind": "fixed", "notes": "One part-time person"}
      ],
      "milestones": [
        {"title": "Ten installers logging jobs weekly", "success_criterion": "Ten accounts active",
         "owner": "Swayam", "due_date": "2026-06-01", "horizon": "now", "status": "in_progress",
         "sort_order": 1, "completed_at": null}
      ],
      "kpis": [
        {"name": "Activated installers", "unit": "installers", "direction": "up",
         "baseline": 0, "target": 40, "target_date": "2026-08-01", "cadence": "monthly",
         "readings": [{"value": 12, "recorded_on": "2026-05-01", "note": "First week"}]}
      ]
    }
  ]
}
```

## Field rules

| Field | Accepted | Fallback |
|---|---|---|
| `stage` | `idea`, `validating`, `building`, `growing` | `idea` |
| `horizon` (venture) | `90 days`, `6 months`, `12 months`, `3 years` | `90 days` |
| `currency` | `INR`, `USD`, `EUR`, `GBP` | `INR` |
| `canvas[].block` | problem, customers, value, solution, channels, revenue, costs, metrics, advantage | row skipped if unknown |
| `swot[].quadrant` | `strength`, `weakness`, `opportunity`, `threat` | row skipped if unknown |
| `swot[].impact` | 1–5 | clamped into range |
| `streams[].model` | subscription, usage, one_off, retainer, marketplace, services | `subscription` |
| `streams[].price`, `volume` | non-negative integers | 0 |
| `streams[].confidence` | `low`, `medium`, `high` | `medium` |
| `costs[].kind` | `fixed`, `variable` | `fixed` |
| `costs[].amount` | non-negative integer, monthly | 0 |
| `milestones[].horizon` | `now`, `next`, `later` | `now` |
| `milestones[].status` | `planned`, `in_progress`, `done`, `at_risk` | `planned` |
| `milestones[].due_date` | ISO date or ISO datetime | `null` |
| `kpis[].direction` | `up`, `down` | `up` |
| `kpis[].cadence` | `weekly`, `monthly`, `quarterly` | `monthly` |
| `kpis[].readings[].recorded_on` | ISO date | row skipped if unreadable |
| `narrative_source` | `local` or `claude` | `local` |

Two readings for the same KPI on the same day are not both loaded: the first is kept and later
duplicates are counted as skipped, matching the unique `(kpi_id, recorded_on)` rule in the database.
Money is a whole number in the venture's own currency — there is no conversion, so do not mix
currencies inside one venture.

## How duplicates are avoided

Idempotency is **by venture name per account**. On import, if a venture with that name already exists
for the account, the whole venture is skipped — canvas, SWOT, streams, costs, milestones, KPIs and
readings included. That means importing the same file twice duplicates nothing. It also means an
edited export will not merge into an existing venture: delete or rename the old one first, or import
into a fresh account.

Child rows without a usable title or text are skipped individually; a bad row never aborts the whole
file. A venture whose name is blank after trimming is ignored.

## Loading it

Create your account in the app first, then:

```powershell
cd "C:\Users\Swayam Naik\TOP-50-CLAUDE-PROJECTS\PROJECT_09\backend"

# See what would happen, without writing anything
.\.venv\Scripts\python.exe -m scripts.import_data --email you@example.com keystone-export.json --dry-run

# Import for real
.\.venv\Scripts\python.exe -m scripts.import_data --email you@example.com keystone-export.json
```

The command prints a count of ventures imported and skipped. It exits with an error if the file is
not a Keystone export, or if the email does not match an existing account.

## Where the data lives

- **Database:** `PROJECT_09/data/keystone.db` by default (the preview uses `data/demo.db`). Both are
  git-ignored and never leave your machine.
- **Export:** a file you download yourself; Keystone does not upload it anywhere.
- **Screenshots and test data:** the repository's demo ventures are invented and marked as such.

## What leaves the machine

Nothing, unless you press **Rewrite with Claude** and an `ANTHROPIC_API_KEY` is configured. In that
one case the venture's name, one-liner, stage, segment, the six brief sections and the local memo are
sent to `api.anthropic.com`; the response is validated before it is stored. Every other feature —
canvas, SWOT, revenue, plan, KPIs, export and import — is local. There is no telemetry, no CDN and no
analytics.

## Deleting your data

- Delete one venture: open it → **Delete**, then type its name exactly. Its child rows go with it.
- Delete everything: Settings → **Delete account**, enter your password and type `DELETE`. Every
  venture, child row and session is removed, and you are signed out.
- Keep a copy first: Settings → **Download JSON export**. The export is the only backup Keystone makes.

## Demo data is labelled

The seeded demo account (`demo@keystone.example` / `keystone-demo`) contains two invented ventures:
**Sahaj**, a complete solar-installer software example, and **Second Draft**, a thin idea-stage
example. Every customer, price, KPI and milestone in them is fabricated for the demo. They are not
the author's real business and should not be read as advice.

## What would help most

If you want to share your own material, send:

1. **Venture names and one-liners** — enough to make the portfolio feel real.
2. **The money model** — price, volume and monthly cost per venture, with the currency.
3. **Three milestones and two KPIs** — the plan and the pace are what the brief is best at.

A JSON export is ideal because it round-trips exactly. Plain text is fine too; it can be typed in or
turned into an export by hand.
