# PRD: Email Command Center (Project 07), "Switchboard"

**Status:** Implemented in v1.0 (2026-11-15) · **Owner:** Swayam · **Category:** Personal Productivity & Life Management

## 1. Problem

An inbox is ordered by arrival, not by consequence. A question from a customer, a receipt, a
newsletter and a note from your boss all occupy the same row, so the work of deciding what matters
happens in your head, every time.

Worse, the decision is lost as soon as it is made. A reply moves the thread out of sight; three days
later nobody remembers who owes what. "Smart inbox" products often replace that mental work with an
opaque score, and they ask for permanent access to the mailbox to produce it.

Switchboard addresses four failures:

- **Route, do not rank by recency.** Five explicit routes — Needs reply, Waiting, FYI, Newsletter,
  Receipt — with the signals that chose one shown in the UI.
- **Keep the open loop visible.** A follow-up is attached to the thread, has an optional date, and
  appears on the dashboard until it is done.
- **Explain the score.** Every point has a sentence. If the score is wrong, you can see which signal
  caused it and override the route.
- **Do not ask for mailbox credentials.** Mail arrives by paste, `.eml` upload or a local JSON
  import. No IMAP, no OAuth, no SMTP, no app password.

AI must work **without a paid API key**. The local writer is the default and the fallback. Claude is
optional, validated, and labelled whenever it is used.

## 2. Target users

| User | Situation | What they need |
|---|---|---|
| The operator | Handles a busy personal or founder inbox | A short list of what needs an answer, and proof of why |
| The freelancer / consultant | Runs several client threads alone | One private desk with per-account isolation and no SaaS account |
| The privacy-conscious user | Will not grant mailbox access to a third party | Local intake, local SQLite, and an opt-in model path only |
| The returning user | Was waiting on a person, not a ticket | A follow-up list grouped by date, with overdue items first |
| The writer | Replies to the same kinds of mail every week | A scaffold that quotes the ask and leaves the commitment to them |

Primary persona: **one person who triages their own mail and wants to stop re-reading the same
threads**, not an IT department running a shared helpdesk.

## 3. Use cases

1. **Morning triage.** Open the dashboard, read the six highest-scoring threads, answer the VIP
   question first.
2. **A message arrives outside the app.** Paste it into Log an email; the rules route it and write a
   summary before it reaches the inbox.
3. **A saved `.eml`.** Upload the file; headers fill in From, To, Subject and arrival time, and the
   `Message-ID` prevents a second import.
4. **A thread needs a different route.** Set it manually; the choice is remembered and new mail no
   longer overwrites it.
5. **"Why is this at the top?"** Open the thread and read every reason and its points.
6. **Reply.** Generate a local draft in warm, brief or formal tone, edit it, copy it into the real
   mail client, then mark it sent so the desk knows the ball moved.
7. **Waiting on a person.** Add a follow-up ("Signed contract from Arjun", due Friday); it appears
   under Next seven days, then Overdue.
8. **Newsletter clean-up.** Use the Newsletter view to confirm that bulk mail stayed out of the reply
   queue.
9. **Search.** Find a thread by a phrase from the body, not just the subject.
10. **Data ownership.** Export every thread, draft and follow-up as JSON; import it into a fresh
    account; delete the account completely.
11. **Phone check.** Read the priority inbox on a phone without horizontal scrolling.
12. **Privacy check.** Confirm in Settings that no key is set and no mailbox is connected.

## 4. MVP scope (implemented)

### Accounts and access
- Register with name, email, password and IANA timezone; sign in and sign out.
- `scrypt` password hashing; server-side sessions stored as token hashes; `HttpOnly`,
  `SameSite=Lax` cookie; CSRF token on every mutation.
- Per-user isolation of mailboxes, threads, messages, drafts and follow-ups. Cross-account ids
  return `404`.
- Login limiter: 10 failures per 15 minutes per client. AI limiter: 8 model calls per 10 minutes per
  account.

### Intake
- Three sources: pasted fields, a `.eml` upload up to 2 MB, and a JSON import script.
- Required: a sender containing `@` and a non-empty body. Subject may be empty and becomes
  `(no subject)`.
- Arrival time: a pasted `datetime-local` is interpreted in the user's timezone; an `.eml` uses its
  `Date` header when parseable; otherwise "now".
- Threading: reply prefixes are stripped, whitespace collapsed and compared inside one mailbox. A
  closed thread is not reused.
- A `Message-ID` already stored is ignored, so uploading the same file twice is harmless.

### Triage
- Five routes: `reply`, `waiting`, `fyi`, `newsletter`, `receipt`.
- Precedence: newsletter wording, receipt wording, then question/request/VIP, then FYI.
- A VIP sender lands in Needs reply unless the mail is clearly bulk or a receipt.
- Manual routes are stored with `category_source="you"` and survive new inbound messages.
- After a reply, the thread moves to Waiting on them unless the user had set the route manually.

### Priority
- Integer score capped at 100, visible on the thread and summarised on the row.
- Points: route base (reply 30, waiting 12, fyi 8, newsletter/receipt 2), VIP 22, unread 8,
  starred 15, question 8, deadline 12, recency 8 / 5 / 2 by age.
- Reasons are listed in the order they contributed; nothing is hidden inside a model.

### Summary
- Local: the first one or two sentences of the latest inbound message, with greeting, quoted history
  and signature removed. Stored with `summary_source="local"` and a note explaining the method.
- Claude: optional, JSON `{"summary": ...}`, 12–800 characters after whitespace normalisation.
  Invalid output falls back to local and records an honest note.

### Drafts
- Local scaffold in warm, brief or formal tone. It quotes the ask when one is found, opens with the
  sender's first name, appends the user's signature, and never invents an amount or a commitment.
- Claude: optional, JSON `{"subject": ..., "body": ...}`, subject must start with `Re:` and body must
  be at least 20 characters.
- Drafts can be edited, copied and deleted. **Mark sent** records an outbound message locally and
  moves the thread to Waiting. It cannot be done twice.

### Follow-ups
- Title (3–240 characters) and an optional due date parsed from `tomorrow`, `today`, `next week`,
  weekdays, `by Friday` or an ISO date.
- Grouped Overdue, Today, Next seven days, Later and No date, using the user's local date.
- Complete, reopen, edit and delete. A completed row keeps a completion timestamp.

### Views and search
- Dashboard, Priority inbox, All, five route views, Starred, Closed.
- Search across subject, participant string and every message body, scoped to the account.
- Mailbox filter. An unknown view falls back to Priority rather than erroring.

### Settings and data
- Name, timezone, signature, VIP list, mailbox labels (default mailbox cannot be removed; a mailbox
  with threads cannot be removed).
- Password change ends other sessions but keeps the current one.
- JSON export (`switchboard-export-v1`) contains no passwords, tokens or keys.
- Account deletion requires the password and the typed word `DELETE`, and removes all children in
  one transaction.

### UI
- Paper-and-ink palette, aubergine rail, amber and vermilion accents, serif headings, routing-slip
  rows.
- Dark variant from `prefers-color-scheme`; the rail becomes a top bar below 900 px.
- Keyboard focus states, toasts, empty states, and confirmation before destructive actions.
- Every core action works without JavaScript; HTMX is used only to smooth mutations.

## 5. Out of scope (v1.0)

- IMAP, POP3, Exchange, Gmail or Outlook connections; OAuth; SMTP sending.
- Attachments beyond the text of a message; calendar invites; contact books.
- Multi-user teams, sharing, assignment or comments.
- Mobile push, email reminders or background sync.
- Semantic/vector search; the archive is small enough for a literal, case-insensitive match.

## 6. Success criteria

| Criterion | How it is checked |
|---|---|
| A pasted message is routed and summarised in one action | `test_ingest.py`, `test_triage.py` |
| Reply prefixes thread correctly and closed threads split | `test_ingest.py` |
| A duplicate `Message-ID` creates no second message | `test_ingest.py` |
| Every route is reachable from explicit wording | `test_triage.py` |
| A VIP is never buried in FYI | `test_triage.py`, `test_threads.py` |
| Every priority point has a reason | `test_triage.py`, thread page |
| A manual route survives new mail | `test_ingest.py` |
| Mark sent records one outbound message and moves to Waiting | `test_drafts.py` |
| Cross-account ids return `404` everywhere | all feature test files |
| Export → import is lossless and idempotent | round-trip script, `test_settings.py` |
| No horizontal scroll at 390 px | Playwright capture with `scrollWidth === innerWidth` |
| Clean install runs without a key | preview on a fresh database |

## 7. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Rules misroute unusual prose | Show the reasons; make the route a one-click override that is remembered |
| A model invents a commitment | Local draft never states an amount; Claude output is length-checked, and every draft is labelled with its writer |
| Users expect real mail sync | The intake page says, in plain words, that there is no connection and no password field |
| Duplicate imports | `Message-ID` dedupe plus the export importer's mailbox/subject/first-message key |
| Sensitive mail leaves the machine | No key by default; the local writer is in-process; the Claude path sends only the latest message and participants |
| SQLite contention from a second process | Writes are short and transactional; the importer is safe to run beside the app |

## 8. Milestones

| Milestone | State |
|---|---|
| Schema, auth, sessions, CSRF, security headers | Done |
| Intake (paste, `.eml`), threading, dedupe | Done |
| Rules, priority, summaries | Done |
| Dashboard, inbox views, search, thread detail | Done |
| Drafts (local + Claude), mark sent | Done |
| Follow-ups and grouping | Done |
| Settings, export, importer, account deletion | Done |
| 201 tests, demo seed, preview, screenshots, docs | Done |
| Tag `project-07-v1.0` and push | Done at release |

## 9. Open questions for a future version

- Should a follow-up be able to exist without a thread (a plain reminder)?
- Is a saved view worth the schema, or is search enough?
- Would a local, offline embedding model materially improve search on a 10,000-message archive?
- Should "mark sent" optionally copy the draft to the clipboard in the same click?
