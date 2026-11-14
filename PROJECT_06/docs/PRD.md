# PRD: Meeting Memory Assistant (Project 06), "Quorum"

**Status:** Implemented in v1.0 (2026-11-14) · **Owner:** Swayam · **Category:** Personal Productivity & Life Management

## 1. Problem

The useful part of a meeting is small: a few decisions, a few commitments, and the reason behind
them. Most of that disappears into a document nobody reopens. Three months later the team remembers
that something was decided, but not what, when, or who agreed to do it.

Existing tools solve the wrong half. Note apps store text; task managers store tasks; chat stores
chronology. None of them reliably turns a pasted transcript into a decision log that can be searched
later, and none of them keep the original notes attached to the extracted record.

Quorum addresses four failures:

- **Discussion and decision are separated.** Only an agreement is logged as a decision.
- **Follow-ups are concrete.** Each has a title, an optional owner and an optional due date.
  Missing information stays missing rather than being invented.
- **The source survives.** The original notes are stored and can be reopened from the record.
- **The archive is searchable.** One query looks across meeting summaries, notes, decisions and
  follow-ups, scoped to one account.

Extraction must work **without a paid API key**. A deterministic local extractor is the default and
the fallback. Claude is optional, validated, and clearly labelled when it is used.

## 2. Target users

| User | Situation | What they need |
|---|---|---|
| The meeting owner | Runs a weekly product or client call and writes rough notes | A fast way to turn notes into decisions and owners |
| The project lead | Has to answer "why did we choose this?" months later | A searchable decision log with dates and links to the source |
| The freelancer / consultant | Keeps notes for several clients in one place | One private archive, per-account isolation, no SaaS account |
| The privacy-conscious user | Will not upload meeting content to an unknown service | A local app, local SQLite, and an opt-in model path only |
| The returning user | Was not in the meeting but owns a follow-up | A clear list of what they owe, grouped by date |

Primary persona: **one person who records meetings and needs to remember what was settled**, not a
whole company looking for a shared workspace.

## 3. Use cases

1. **After a call.** Paste rough notes with a title, date and attendees; Quorum returns a summary,
   the decisions, and the follow-ups with owners and dates.
2. **Morning review.** Open Follow-ups, see overdue and today's items, complete one and reschedule
   another.
3. **Decision archaeology.** Search "pricing" in Memory; open the meeting that settled it and read
   the original paragraph.
4. **Correction.** A decision was recorded slightly wrong; add a missing decision or edit the record
   without rebuilding everything.
5. **New notes for an old meeting.** Ticking **Re-read the notes** replaces the extracted items after
   an edit, while a normal save preserves manual additions.
6. **Ownership check.** Filter follow-ups by Priya to see everything she left with.
7. **Status drift.** A decision marked Revisit is easy to find; when the team settles it, flip it back
   to Agreed.
8. **Data ownership.** Export the whole archive as JSON, import it into a fresh account, or delete
   the account completely.
9. **Privacy check.** Confirm in Settings that the local extractor is active and that no key is set.
10. **Phone capture.** Paste notes from a phone after a call without a desktop layout breaking.

## 4. MVP scope (implemented)

### Accounts and access
- Register with name, email and password; sign in and sign out.
- Password hashing, server-side sessions, `HttpOnly` / `SameSite=Lax` cookie, CSRF on all mutations.
- Per-user isolation of every meeting, decision and follow-up. Cross-account ids return `404`.

### Capture
- Fields: title (3–160), meeting date, attendees, notes or transcript (20–60,000 characters).
- Extraction produces a summary, 0–8 decisions and 0–12 follow-ups with optional owner and due date.
- The meeting row stores whether the result came from `local` or `claude`, plus the model id and a
  short note explaining a fallback.
- `@mentions` in the notes are added to the attendee list, without duplicates.

### Local extractor
- Inline and block section headers: summary/overview, decisions, action items/actions/next steps,
  attendees/participants.
- Bullet styles `-`, `*`, `•`, `–`, `—`, `1.`, `1)`.
- Decision prefixes such as `Decision:`, `We agreed`, `Approved`, `It was agreed`.
- Action prefixes such as `Action:`, `TODO:`, `Next step:` and `Follow-up:` (colon required for the
  last two so "Follow up with legal" is not truncated).
- Owners from `@mention`, `Owner:`, `Name will…`, or an attendee name at the start of an action.
- Due dates from ISO dates, weekdays (next occurrence), `today`, `tomorrow`, `next week`, `EOD`.
- Deduplication, length clamps and safe behaviour on empty or unusual input.

### Claude path (optional)
- Enabled only when `ANTHROPIC_API_KEY` is non-empty.
- Sends the meeting metadata and notes to the Messages API, requesting strict JSON only.
- Validates the response type, item counts, text lengths and date range before storage.
- Any failure (network, timeout, non-200, invalid JSON, empty result) returns the local result with a
  visible note; the UI never silently claims Claude was used.

### Meetings
- Newest-first archive with search and a source filter.
- Detail page: summary, record metadata, decision log, follow-ups, original notes, print view.
- Edit title/date/attendees/notes; optional re-extraction; delete with confirmation.
- Moving the meeting date moves every decision's `decided_on` with it.

### Decisions
- Add, delete, and flip between Agreed and Revisit.
- Decision log with search and status filter.
- Each decision is linked to its meeting and date.

### Follow-ups
- Add, complete, reopen, edit and delete.
- Grouped into Overdue, Today, This week, Later and No date using the user's timezone.
- Filters for Open / Done / All, plus an owner filter.
- Same-site-only redirect target on actions, preventing open redirects.

### Memory
- One search over meeting title, notes and summary; decision text; follow-up title and owner.
- Results grouped by type and linked back to the meeting.
- Scoped to the signed-in account.

### Settings
- Display name and IANA timezone.
- Password change that invalidates other sessions.
- JSON export (`quorum-export-v1`).
- Account deletion requiring the password and the word `DELETE`.

### UI and operations
- Responsive desktop, tablet and phone layouts; light and dark themes.
- Empty states, error states, toasts, focus styles and print styles.
- `/health`, security headers, custom 404/422 pages.
- Alembic migration, demo seed, preview server and JSON importer.

## 5. Advanced features (post-MVP)

- Audio upload with a local, free speech-to-text model and speaker attribution.
- Revisit reminders: a date on a Revisit decision and a "needs another look" queue.
- People and topic pages that pivot the Memory archive beyond a single query.
- Diff view when re-reading notes, so replaced decisions are visible before saving.
- Markdown/plain-text import in addition to Quorum JSON.
- Read-only JSON API for a native client.
- Shared team archive (requires a real authorization model and is out of scope for v1).

## 6. Out of scope

- Live meeting recording, transcription, diarisation or video.
- Calendar, email or chat integrations and automatic reminders.
- Paid AI, paid hosting, subscriptions or ads.
- Mobile native apps.
- Legal, HR or compliance advice. Quorum records what was said; it does not decide what is allowed.
- Multi-tenant hosting, team workspaces or administrator roles.

## 7. User stories

| # | As a… | I want to… | So that… |
|---|---|---|---|
| 1 | new user | create an account and paste my first meeting | I see the value before learning the app |
| 2 | meeting owner | get a summary, decisions and follow-ups from rough notes | I do not rewrite the meeting by hand |
| 3 | owner | see which follow-ups are overdue or due today | I start the day with the right work |
| 4 | owner | complete a follow-up from the list | closing the loop takes one click |
| 5 | owner | edit an owner or due date | extraction mistakes are cheap to correct |
| 6 | project lead | search a topic across meetings, decisions and actions | I find the context, not just a task |
| 7 | project lead | open the original notes from a record | I can check what was actually said |
| 8 | returning user | filter follow-ups by person | I can prepare for a one-to-one |
| 9 | careful user | mark a decision Revisit and find it later | status drift is visible |
| 10 | user with revised notes | re-read the notes and rebuild the record | the archive reflects the better source |
| 11 | privacy-conscious user | confirm no model key is configured | my notes stay on the machine |
| 12 | phone user | capture and triage from a small screen | I do not need a desktop after every call |
| 13 | data owner | export or delete everything | I stay in control of my archive |
| 14 | user with a wrong clock | set my IANA timezone | Overdue and Today match my day |

## 8. Key flows

### First capture
`/register` → session cookie → empty dashboard → **New meeting** → title, date, attendees, notes →
`POST /meetings` → local or Claude extraction → meeting detail with summary, decisions and
follow-ups → redirect target `/meetings/{id}?created=1`.

### Daily triage
`/` or `/actions` → overdue group → complete a follow-up (`POST /actions/{id}/toggle`) → row moves
to Done and counts recompute → edit a due date inline if it slipped.

### Decision archaeology
`/memory?q=pricing` → grouped results → open the meeting → read the decision and its date → open
**The original notes** to see the paragraph it came from.

### Correcting a record
Meeting detail → **Edit** → change the text or date → save without re-extraction keeps manual items;
tick **Re-read the notes** and save to replace them. Editing the date moves every decision with it.

### AI fallback
With a key, a network failure or malformed JSON stores the local extraction plus
`Claude was unavailable or returned an invalid result; the local extractor was used.` The detail page
shows that note in an info banner. Without a key, every record says
`Local extractor: rules only, no model call.`

### Data portability
Settings → **Download JSON** → `quorum-export.json` → optional `import_data.py` into another account.
Identical meetings (same title and date) are skipped, so the import can be run twice.

## 9. Non-functional requirements

| Area | Requirement |
|---|---|
| Performance | Dashboard and archive render in well under a second for 500 meetings and 2,000 follow-ups on a laptop; indexes on `(user_id, occurred_on)`, `(user_id, decided_on)` and `(user_id, status, due_date)` |
| Security | Hashed passwords, hashed session tokens, CSRF, CSP and security headers, per-user authorization, same-site redirect validation, no secrets in the repository |
| Privacy | Local-only by default; no analytics, no third-party scripts; Claude is opt-in and receives only meeting metadata and notes, never the password, email or session cookie |
| Accessibility | Semantic headings, labelled controls, visible focus, keyboard-operable buttons, respect for reduced motion, contrast checked in both themes |
| Reliability | Alembic migrations on startup, deterministic seed through the real extractor, graceful AI fallback, consistent 404/422 pages, no data loss on failed form submissions |
| Portability | One Python process; no Node build; works on Windows, macOS and Linux; the SQLite file is the only state |
| Maintainability | Routes → services → models separation; one responsibility per module; tests for extraction rules, every route family and every AI fallback |

## 10. Success criteria

A release is complete only when all of the following are true:

- [x] A new account can register, capture a meeting and see the extracted record.
- [x] Decisions are separate from the summary and link back to the meeting.
- [x] Follow-ups have an owner and due date when the notes provide them, and stay blank when they do not.
- [x] The local extractor handles headings, bullets, prefixes, mentions and the supported due phrases.
- [x] Claude output is validated and clamped; every failure falls back to the local result with a visible note.
- [x] Overdue / Today / This week / Later / No date grouping uses the account timezone.
- [x] Completing, reopening, editing and deleting a follow-up all persist correctly.
- [x] Decision status can be flipped and filtered.
- [x] Memory search covers meetings, decisions and follow-ups and never crosses accounts.
- [x] Importing the same export twice does not duplicate a meeting.
- [x] Export contains meetings, decisions and follow-ups and no password material.
- [x] Account deletion removes access and invalidates the session.
- [x] 144 automated tests pass on a clean database.
- [x] Screenshots are captured from the running app, not mocked.
- [x] README, PRD, architecture and data guide are complete.
