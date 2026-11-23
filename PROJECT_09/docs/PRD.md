# PRD: Business Strategy Planner (Project 09), "Keystone"

## 1. Problem

Most strategy tools optimise for a document that looks finished. They ask for a market size, a
competitor grid and a five-year projection, then reward the person who fills every box with a
confident number. The result is a deck that cannot be maintained: nobody knows which figures were
guesses, the plan drifts from the calendar, and the "KPIs" are a static list with no pace.

A founder planning alone needs the opposite. The artefacts should be small enough to keep current,
the gaps should be visible, and every derived number should be reproducible from the inputs on the
same screen. When something is a guess, the tool should say so.

Keystone starts from four constraints:

1. **No invented data.** No market feed, no crawler, no benchmark database, no currency conversion.
2. **Derived numbers are always explainable.** Margin, break-even, scenario revenue, KPI pace and
   overdue are computed on read from rows the user can see.
3. **Empty is a valid state.** A new venture reads as thin, with the next three gaps named, rather
   than as a template with placeholder confidence.
4. **AI is optional and labelled.** The brief works offline; Claude only improves prose when a key
   exists, and the UI never hides which one produced the memo.

## 2. Target users

- **A solo founder or indie hacker** running one or two small products, who needs the money model
  and the plan in one place instead of a spreadsheet plus a task app.
- **A consultant or fractional operator** shaping a client's idea into a canvas, a costed model and a
  ninety-day plan, then handing over a one-page brief.
- **A small team's "business person"** who keeps the strategy desk while engineers keep the product,
  and who needs KPI pace visible without building a BI stack.
- **A student or first-time founder** learning the vocabulary, who benefits from prompts in each
  empty block and arithmetic that shows its working.

The common thread: one person, a handful of ventures, no analyst, no data subscription, and a strong
preference that private plans stay on their own machine.

## 3. Use cases

1. **Shape a new idea.** Create a venture with a one-liner, stage and currency. Fill the nine canvas
   blocks over a few sittings; the overview keeps naming the next empty block.
2. **Pressure-test the money.** Add two or three streams with price, volume and confidence, add
   fixed and variable costs, then switch between conservative, base and upside to see where the
   margin breaks.
3. **Write an honest SWOT.** Add items with an impact from 1 to 5. The ledger tells you whether the
   weighted balance leans strong or exposed, and lists the three negative items that matter most.
4. **Plan ninety days.** Put milestones in now / next / later with due dates and owners. Anything not
   done and past its date is marked overdue without anyone updating a status.
5. **Track a few KPIs.** Set a baseline, target and target date, then log values. The page compares
   progress with elapsed time and says ahead, on track, behind or missed.
6. **Generate the brief.** Open the brief, read six grounded sections and the memo, edit by saving
   the local version, optionally ask Claude for a rewrite, then print.
7. **Review the portfolio.** See every live venture with canvas completeness, base MRR, plan progress
   and how many KPIs are behind, then open the one that needs attention.
8. **Archive and export.** Archive a venture that is paused, keep it in the export, and re-import the
   JSON into another account without duplicating anything.

## 4. MVP scope (implemented)

### Accounts and access

- Email + password registration and login, with a name and an IANA timezone.
- scrypt password hashes (N=2^14, r=8, p=1), SHA-256 session-token hashes, 30-day sessions.
- CSRF token on every state-changing form, a login limiter (10 failures / 15 minutes) and an AI
  limiter (12 calls / 10 minutes).
- CSP `default-src 'self'`, `script-src 'self'`, `frame-ancestors 'none'`; no CDN, no inline script.
- Changing the password ends every other session. Every row is owner-scoped; another account's id is
  a 404.

### Ventures

- Create, edit, archive/restore and delete a venture. Names are unique per account.
- Fields: name, one-liner, stage (idea / validating / building / growing), planning horizon, currency
  (INR / USD / EUR / GBP), market, segment, alternatives and differentiation.
- Portfolio page with live and archived lists, canvas completeness, base MRR, plan progress and KPI
  counts; a venture overview with a snapshot and up to three next moves.
- Deleting requires typing the venture name exactly.

### Nine-block canvas

- Blocks: problem, customer segments, value proposition, solution, channels, revenue, costs, metrics
  and unfair advantage.
- Multiple entries per block, each with a title and an optional detail; add, edit and delete.
- Completeness counts a block once it has an entry. Empty blocks render a prompt explaining what
  belongs there.

### Impact-weighted SWOT

- Strengths, weaknesses, opportunities and threats, each with an impact from 1 to 5 and optional
  evidence; add, edit and delete.
- Counts and impact totals per quadrant; positive vs negative balance with a ±3 band and a tone label.
- The three highest-impact negative items are surfaced as current risks.

### Revenue model

- Streams: pricing model (subscription, usage, one-off, retainer, marketplace, services), name,
  whole-unit price, unit label, monthly volume, confidence (low / medium / high), notes.
- Costs: name, monthly amount, fixed or variable, notes.
- Derived: base MRR, ARR, weighted MRR, volume, fixed and variable cost, total cost, margin, margin
  percent, blended price, break-even units and revenue share by pricing model.
- Three scenarios that scale volume (×0.7, ×1.0, ×1.4) with a side-by-side table.
- Empty model or empty costs produce an explicit "not costed" state instead of a fake zero.

### Plan

- Milestones: title, success criterion, owner, optional due date, horizon (now / next / later) and
  status (planned / in progress / done / at risk); add, edit, change status and delete.
- Derived overdue (not done and past due), completed timestamp, per-horizon counts and progress.
- Grouped, ordered lists with overdue first inside a horizon.

### KPI plan

- KPIs: name, unit, direction (up / down), baseline, target, optional target date, cadence; add, edit
  and delete.
- Readings: value and note, one per KPI per day; add and delete.
- Derived status: reached, ahead, on track, behind, missed or no readings, using elapsed-time pace
  with a ±10-point tolerance; a fallback midpoint rule when no target date exists, stated on the page.
- Inline SVG sparkline for two or more readings; an "attention" list ordered by severity.

### Brief

- Six sections and a memo assembled locally from the canvas, model, plan, KPI log and SWOT.
- Explicit missing-state sentences; never invents a number.
- Draft until saved; then labelled Local, with a reset action.
- Optional Claude rewrite: strict JSON, 2–6 paragraphs, 240–3,600 characters, no headings or fences,
  any failure leaves the saved memo untouched and says why. Labelled Claude on success.
- Print-friendly layout.

### Settings and data

- Name, timezone (validated), password change, live counts for every entity.
- `keystone-export-v1` JSON export covering ventures and every child row; no secrets.
- Account deletion requiring the password and the word `DELETE`, removing every row and the session.
- Idempotent importer keyed by venture name, with `--dry-run`, clamping and safe defaults.

### UI

- Server-rendered Jinja2; every core action works with JavaScript disabled.
- HTMX for in-place actions where it improves the flow.
- Ink rail, blueprint paper, cobalt accents, mono uppercase labels; dark theme following the OS.
- Rail collapses to a wrapped top bar under 900 px; no horizontal scroll at 390 px.
- Visible "Built by Swayam" credit.

## 5. Out of scope (v1.0)

- Market sizing, competitor scraping, benchmarks, exchange rates or any external data feed.
- Currency conversion or summing different currencies.
- Tax, invoicing, accounting, payroll, cash-flow timing or a full financial model.
- Churn, cohort retention, LTV/CAC modelling or annual discounting.
- Multi-user teams, roles, sharing, comments or approvals.
- File attachments, images, pitch-deck export or a public share link.
- Mobile apps, notifications, email digests or calendar sync.
- Public deployment, a JSON API for third parties, or an AI mode that invents facts.

## 6. Success criteria

- A new user can register, create a venture, fill all nine canvas blocks, add a stream and a cost,
  add a milestone and a KPI with a reading, and read a brief without documentation.
- Every derived number on screen can be recomputed by hand from the visible inputs.
- An empty venture shows explicit missing-state text in the brief, not placeholder confidence.
- A second import of the same export creates zero duplicate ventures or child rows.
- The whole test suite passes from a clean environment with no API key and no network.
- Desktop, dark and 390 px layouts render without horizontal scroll, and every page has a visible
  credit.
- No secret — password, session token, CSRF token or API key — appears in an export.

## 7. Risks and mitigations

| Risk | Mitigation |
|---|---|
| A confident memo hides weak inputs | Sections state what is missing; the memo never adds a number that is not stored |
| Money arithmetic drifts from the rows | Integer whole units, derived on every read, one currency per venture, no cross-currency sums |
| Overdue items go stale | Overdue is computed from the due date on every request, never stored |
| KPI status looks arbitrary | Pace is progress vs elapsed time with a documented ±10 band, and the expected value is shown |
| The Claude path breaks the memo | Strict validation, a strict timeout, a visible failure note and the local memo kept unchanged |
| Cross-account leakage | Every query filters by `user_id`; foreign ids return 404; tests cover two accounts |
| CSRF or XSS regressions | CSRF on every form, autoescape on, CSP with no inline script, tests for both |
| Data loss on import | Dry run, idempotency by name, clamped values, no partial venture on a skip |
| The demo looks like real advice | Demo ventures are clearly invented; the README and YOUR_DATA say so |

## 8. Milestones

1. **Schema and auth** — users, sessions, ventures and child tables; migration `0001`; register,
   login, logout, CSRF, rate limits.
2. **Venture workspace** — portfolio, create/edit, archive, name-confirmed delete, overview snapshot.
3. **Canvas and SWOT** — nine blocks with completeness and gaps; impact-weighted SWOT with risks.
4. **Revenue model** — streams, costs, derived summary, scenarios and model split.
5. **Plan and KPIs** — horizons, derived overdue, status transitions; progress, pace, statuses and
   sparklines.
6. **Brief and AI** — six sections, local memo, save/reset, Claude rewrite with validation.
7. **Settings and data** — profile, password, export, importer, account deletion.
8. **Tests, screenshots and docs** — 332 tests, twelve genuine captures, README, PRD, architecture
   and data guide.

All eight are complete for v1.0.

## 9. Open questions for a future version

- Should confidence be backed by an evidence note per stream, and should the brief cite it?
- Is a monthly MRR/cost snapshot worth the extra table, or does it invite false precision?
- Should scenarios allow per-stream factors instead of one global volume multiplier?
- Would a decision log (what changed, when, which number moved) be more useful than a narrative memo?
- How should a portfolio compare ventures in different currencies without implying a conversion?
- Should the importer support merge-by-name as well as skip-by-name?
