# Architecture: Keystone (Project 09)

## 1. Shape

```text
Browser ──HTML forms / small HTMX──▶ FastAPI (Jinja2, server-rendered)
                                       ├── routes/auth.py      register · login · logout
                                       ├── routes/ventures.py  portfolio · venture · brief
                                       ├── routes/canvas.py    nine blocks
                                       ├── routes/swot.py      weighted ledger
                                       ├── routes/revenue.py   streams · costs · scenarios
                                       ├── routes/plan.py      milestones · status
                                       ├── routes/kpis.py      KPIs · readings
                                       ├── routes/settings.py  profile · password · export · delete
                                       ├── services/canvas.py      completeness · gaps
                                       ├── services/swot.py        impact balance · risks
                                       ├── services/finance.py     MRR · margin · break-even
                                       ├── services/milestones.py  horizons · overdue
                                       ├── services/kpis.py        progress · pace · sparkline
                                       ├── services/overview.py    one venture, summarised
                                       ├── services/brief.py       sections · memo · prompt
                                       ├── services/ai.py          optional Claude rewrite
                                       └── SQLAlchemy ──▶ SQLite (data/keystone.db)
                                                          └──▶ api.anthropic.com (optional, key only)
```

One Python process, one SQLite file, no build step and no background worker. Every page is rendered
on the server; HTMX is used only to replace a panel after an action, and all forms work without it.

## 2. Request lifecycle

1. `create_app()` builds settings, the SQLAlchemy engine and two in-process sliding-window limiters.
2. A security middleware sets `Content-Security-Policy`, `X-Content-Type-Options` and
   `Referrer-Policy` on every response.
3. `optional_ctx()` reads the `ks_session` cookie, hashes the token, loads the session and user, and
   derives the user's timezone, local `today` and `now`. A missing or tampered token yields `None`.
4. Page dependencies raise `LoginRequired`, which becomes a `303 /login` for a normal request and a
   `401` with `HX-Redirect` for HTMX.
5. CSRF is checked on every state-changing route: the `x-csrf-token` header or a `csrf_token` form
   field must match the session's token in constant time. Login and register use a short-lived
   `ks_csrf` cookie so a signed-out browser can still submit.
6. The route loads only rows owned by the user, mutates them, commits, and returns `303` to a page
   (or an HTML partial when the request came from HTMX).
7. Errors render a small `error.html` shell with the status and message; HTMX errors use
   `HX-Reswap: none` and an `app-error` toast event.

## 3. Data model

| Table | Columns (besides `id`, `created_at`) | Notes |
|---|---|---|
| `users` | `email` unique, `name`, `password_hash`, `timezone` | scrypt hash, IANA timezone |
| `sessions` | `user_id`, `token_hash` unique, `csrf_token`, `expires_at` | only the SHA-256 token is stored |
| `ventures` | `user_id`, `name`, `one_liner`, `stage`, `horizon`, `currency`, `market`, `segment`, `alternatives`, `differentiation`, `narrative`, `narrative_source`, `narrative_at`, `archived`, `updated_at` | unique `(user_id, name)`; check constraints on stage and currency |
| `canvas_entries` | `venture_id`, `block`, `title`, `detail`, `sort_order` | check constraint on the nine blocks |
| `swot_items` | `venture_id`, `quadrant`, `text`, `impact`, `evidence` | impact is 1–5; quadrant is checked |
| `revenue_streams` | `venture_id`, `name`, `model`, `price`, `unit`, `volume`, `confidence`, `notes` | price and volume are ≥ 0 integers |
| `cost_lines` | `venture_id`, `name`, `amount`, `kind`, `notes` | amount ≥ 0; kind fixed or variable |
| `milestones` | `venture_id`, `title`, `success_criterion`, `owner`, `due_date`, `horizon`, `status`, `sort_order`, `completed_at` | overdue is not stored |
| `kpis` | `venture_id`, `name`, `unit`, `direction`, `baseline`, `target`, `target_date`, `cadence` | direction up or down |
| `kpi_readings` | `kpi_id`, `value`, `recorded_on`, `note` | unique `(kpi_id, recorded_on)` |

Every child table cascades from its venture (and a venture cascades from its user), both in the
foreign key (`ON DELETE CASCADE`) and in the ORM relationship. The migration is
`alembic/versions/0001_initial_schema.py`, revision `0001`.

## 4. Canvas and SWOT arithmetic

**Canvas.** `grouped()` returns the nine canonical blocks, each sorted by `sort_order` then `id`.
`completeness()` counts a block as filled when it has at least one entry and reports the missing
block keys and labels. `gaps()` returns the first three empty blocks with the prompt for each.
`ready()` is true only when every block has at least one entry.

**SWOT.** Impact is an integer 1–5. For each quadrant the ledger keeps a count and an impact total.
`positive` is strength + opportunity impact, `negative` is weakness + threat impact, and
`balance = positive - negative`. The tone is `strong` above +3, `exposed` below −3, `even` in
between, and `empty` when there are no items. Risks are the three highest-impact negative items,
sorted by impact and then id, regardless of quadrant.

## 5. Revenue model

All money is an integer in the venture's currency, per month.

```text
stream_expected(s)  = max(0, price) × max(0, volume)
weighted_mrr        = Σ stream_expected(s) × weight(confidence)
fixed, variable     = Σ amount by kind
total_cost          = fixed + variable
revenue(scenario)   = round(Σ stream_expected(s) × factor)
margin              = revenue − total_cost
margin_percent      = round(margin / revenue × 100)     (None when revenue is 0)
blended_price       = Σ stream_expected(s) / Σ volume
breakeven_units     = ceil(total_cost / blended_price)  (None when blended_price is 0)
```

Confidence weights are low `0.4`, medium `0.7`, high `1.0`. Scenario factors are conservative
`0.7`, base `1.0`, upside `1.4`; scenarios scale volume only. `by_model()` groups expected revenue by
pricing model and returns each model's share, largest first. A blank stream list or a blank cost list
sets `costed = False`, and the template says "not costed" instead of showing a zero margin.

## 6. Plan arithmetic

A milestone is **overdue** when it is not `done` and its due date is before today. `visible_status()`
returns `overdue` in that case and the stored status otherwise. Sorting inside a horizon puts dated
items first by date, then `sort_order` and id, with undated items last. Progress is
`done / total` per horizon and overall. Setting `done` stamps `completed_at`; moving away from `done`
clears it. Nothing about overdue is stored, so a plan read tomorrow is automatically correct.

## 7. KPI progress and pace

```text
progress(value) =
  direction "up":   clamp(0, 100, (value − baseline) / (target − baseline) × 100)
  direction "down": clamp(0, 100, (baseline − value) / (baseline − target) × 100)

expected(today) = clamp(0, 100, elapsed_days / total_days × 100)
                  from the KPI's creation date to its target date
```

The latest reading is the one with the greatest `recorded_on`, then the greatest id. Status rules, in
order: no reading → `no_data`; progress ≥ 100 → `reached`; past the target date → `missed`; no target
date → `on_track` at ≥ 50% else `behind`; otherwise compare `progress − expected` with a ±10 tolerance
(`ahead`, `on_track`, `behind`). The expected value and the delta are shown next to the bar, and the
fallback rule is stated on the page.

`sparkline()` draws a polyline in a 132×34 box with 3 px padding. A flat series sits on the middle
line; one reading or none returns `None` and no chart. Progress is clamped so an overshoot does not
distort the bar, but the raw latest value is always printed.

## 8. Brief assembly and the Claude path

`overview.snapshot()` builds one dictionary from the venture: canvas entries, canvas completeness and
gaps, the finance summary and scenario table, the model split, the plan summary and the KPI summary,
and the SWOT ledger. The pages and the brief read the same snapshot, so a figure cannot differ
between the overview and the memo.

`brief.sections()` returns six blocks in a fixed order:

| Key | Heading | Sources |
|---|---|---|
| `opening` | The opening | name, stage, one-liner, segment |
| `market` | Where it plays | market, alternatives, differentiation, customer and value canvas notes |
| `model` | How it earns | revenue summary, margin, break-even, scenario note |
| `execution` | What happens next | milestone counts, overdue, the nearest milestone |
| `proof` | What would prove it | KPI counts, healthy share, the KPI needing attention |
| `risks` | What could break it | SWOT balance, the three highest-impact negatives |

Each block is a list of plain sentences. An empty section returns an explicit sentence such as
"No revenue streams are defined yet, so the brief cannot make a financial claim." `memo()` joins the
sections into a founder-voice memo and ends with the canvas gaps when any remain. `prompt()` writes
the venture header, the sections and the local memo, then instructs the model to return
`{"narrative": "..."}` and nothing else.

`ai.rewrite()` returns `(narrative, note)`. Without a key it returns `(None, "No API key …")`; with a
key it posts to the Messages API (`max_tokens` 900, the configured timeout) and validates the result:
a string, no `#` and no code fence, 2–6 paragraphs, no paragraph under 40 characters, and 240–3,600
characters after whitespace normalisation. Any HTTP, JSON or validation failure returns
`(None, FALLBACK_NOTE)`. The route saves only a valid narrative and sets `narrative_source` to
`claude`; otherwise the previous memo is untouched and the redirected page shows the reason.

## 9. Route contracts

All routes are server-rendered. A successful state change returns `303` with `Location`; HTMX
requests receive an HTML partial instead. The full table is in the [README](../README.md#10-api-and-form-endpoints).
The important ownership rule is uniform: `_shared.owned_venture()` selects the venture by
`(id, user_id)` and raises `404` when absent, and every child helper resolves its parent through that
function before returning the row.

## 10. Export and import

`GET /settings/export` returns `keystone-export-v1` as an attachment named `keystone-export.json`:

```json
{
  "format": "keystone-export-v1",
  "exported_for": "you@example.com",
  "ventures": [
    {
      "name": "…", "one_liner": "…", "stage": "validating", "horizon": "90 days",
      "currency": "INR", "market": "…", "segment": "…", "alternatives": "…",
      "differentiation": "…", "narrative": "…", "narrative_source": "local",
      "archived": false,
      "canvas": [{"block": "problem", "title": "…", "detail": "…", "sort_order": 1}],
      "swot": [{"quadrant": "threat", "text": "…", "impact": 5, "evidence": "…"}],
      "streams": [{"name": "…", "model": "subscription", "price": 1499, "unit": "per month",
                   "volume": 40, "confidence": "high", "notes": "…"}],
      "costs": [{"name": "…", "amount": 18000, "kind": "fixed", "notes": "…"}],
      "milestones": [{"title": "…", "success_criterion": "…", "owner": "…",
                      "due_date": "2026-06-01", "horizon": "now", "status": "planned",
                      "sort_order": 1, "completed_at": null}],
      "kpis": [{"name": "…", "unit": "…", "direction": "up", "baseline": 0, "target": 40,
                "target_date": "2026-08-01", "cadence": "monthly",
                "readings": [{"value": 12, "recorded_on": "2026-05-01", "note": "…"}]}]
    }
  ]
}
```

There is no password hash, session, CSRF token or API key in the document. The importer reads the
format, falls back for older files that omit it, and rejects anything else. It looks up the account by
email, then processes ventures one at a time: a name that already exists for that account is skipped
**whole**, so a second run duplicates nothing. `_int`, `_float`, `_text`, `_day`, `_moment`, `_choice`
and `_flag` clamp or coerce every value; an invalid child row is skipped rather than aborting the
venture. `--dry-run` performs the whole walk and rolls back instead of committing.

## 11. Security

- **Passwords:** scrypt with `N=2^14, r=8, p=1`, a 16-byte random salt and a 32-byte digest, encoded
  as `scrypt$N$r$p$salt$digest`. Verification uses `hmac.compare_digest`.
- **Sessions:** a 32-byte random token in an `HttpOnly`, `SameSite=Lax` cookie; the database stores
  only its SHA-256. `Secure` follows `COOKIE_SECURE`. Expired sessions are rejected on read.
- **CSRF:** a 32-byte token per session, compared in constant time, required on every POST. Login and
  register use a separate short-lived cookie because there is no session yet.
- **Limits:** login 10 failures / 15 minutes per client, AI rewrite 12 calls / 10 minutes per user,
  both in-process sliding windows.
- **Headers:** CSP `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:;
  frame-ancestors 'none'`, plus `nosniff` and `same-origin` referrer policy.
- **Templates:** Jinja2 autoescape is on for every HTML template. User text is never marked safe.
- **Ownership:** every select is filtered by the signed-in user; foreign ids return `404`.
- **Destructive actions:** venture deletion requires the exact name; account deletion requires the
  password and the word `DELETE`; both are POST-only and CSRF-protected.
- **No secrets in logs or exports:** the API key is read from settings and never written to the
  database or a template. The export test asserts the absence of `password`, `scrypt`, `token_hash`,
  `csrf`, `ks_session` and `api_key`.

## 12. Time

`UTCDateTime` stores naive UTC and returns aware UTC. Every displayed timestamp is converted to the
user's IANA timezone. `local_today()` supplies the date used for overdue and KPI pace, so a user in
Asia/Kolkata sees the correct "today" near midnight UTC. Milestone due dates and KPI target dates are
plain dates, and readings are unique per KPI per calendar day. The demo seed computes dates relative
to the seed run so its overdue and pace labels stay believable.

## 13. Testing strategy

- One temporary SQLite database per test, migrated with Alembic, so tests never touch `data/`.
- A `Browser` helper wraps `TestClient`, follows redirects manually, carries the CSRF token the way
  real pages do, and registers or logs in an account.
- Helpers `add_venture`, `add_canvas`, `add_swot`, `add_stream`, `add_cost`, `add_milestone`,
  `add_kpi` and `add_reading` create rows through the real forms, so validation is exercised too.
- Unit tests cover the arithmetic directly: canvas completeness, SWOT balance, finance summaries and
  scenarios, milestone overdue, KPI progress and pace, sparkline geometry, brief sections, prompt
  text and narrative validation.
- Page tests assert rendered figures and labels (for example ₹77,960), not internal state alone.
- Isolation tests use two accounts and assert that every foreign id is a `404`.
- The AI tests monkeypatch `httpx.post` with a fake response and cover success, invalid prose, HTTP
  errors and network errors. No real key or network call is involved.

## 14. Deliberate omissions

No crawler, no market or competitor feed, no currency conversion, no exchange-rate table, no tax or
cash-flow model, no churn or cohort logic, no teams or sharing, no attachments, no public deployment
and no third-party API other than the optional Anthropic call. These are product decisions, not
unfinished work: each one would either introduce data the user did not enter or imply a precision the
inputs cannot support.
