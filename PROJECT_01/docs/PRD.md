# PRD — Personal Dashboard (Project 01)

## 1. Problem

A person's day is spread across a calendar app, a to-do list, reminder notifications and an
email inbox. Every morning they open four tools to answer one question: *what matters today?*
Context-switching wastes time and things slip through (an overdue task hidden in a list, an
unread email from a client, a meeting that collides with a deadline).

## 2. Target users

- **Primary:** knowledge workers, students and freelancers who manage their own schedule and
  already use a calendar (Google / Outlook / Apple) and an email account.
- **Secondary:** small-team leads who want a personal "command view" before stand-up.

Users are comfortable with web apps; some will self-host on their own machine.

## 3. Use cases

1. Open the dashboard in the morning and read a short briefing of the day.
2. See today's meetings in time order, including those from an external calendar.
3. Pick up to three priorities for the day and tick them off.
4. Capture a task or reminder in a few seconds without leaving the page ("call bank tomorrow 10am").
5. Get a notification when a reminder is due; snooze or dismiss it.
6. See unread / flagged emails that need attention and turn one into a task.
7. Review overdue and upcoming tasks and reschedule them.

## 4. MVP scope (this release)

| Area | Feature |
|---|---|
| Accounts | Register / sign in / sign out; every record belongs to one user; per-user timezone |
| Daily briefing | One-click briefing of today (schedule, tasks, reminders, inbox) with suggested priorities. Uses Claude when `ANTHROPIC_API_KEY` is set; otherwise a deterministic rule-based summary, labelled as such |
| Schedule view | Today's agenda on the dashboard; week view calendar; local events (create / edit / delete) |
| External calendars | Subscribe to an ICS feed URL (e.g. Google "secret address in iCal format") or upload an `.ics` file; recurring events expanded; manual re-sync |
| Task tracker | Tasks with title, notes, priority, due date, status; views: today, overdue, upcoming, all, done |
| Reminders | Reminders at a date/time; in-app + browser notification when due; snooze / dismiss |
| Daily priorities | Up to 3 priorities per day, optionally linked to a task |
| Email | Connect an IMAP mailbox read-only (app password, stored encrypted); sync recent message headers; unread / flagged list; "turn into task" |
| Quick actions | Command bar (Ctrl/⌘+K) with natural-language quick-add for tasks, reminders and events, with a live preview of what will be created; buttons for sync / briefing |

## 5. Out of scope for the MVP (future)

- OAuth integrations (Google Calendar / Gmail API, Microsoft Graph) and two-way calendar sync.
- Sending or replying to email; reading full message bodies.
- Recurring tasks, sub-tasks, shared/team dashboards, mobile push notifications.
- Scheduled background sync (MVP syncs on demand).

## 6. User stories

- *As a user,* I can create an account and my data is private to me.
- *As a user,* I see today's date, my agenda, my due/overdue tasks, upcoming reminders and
  inbox items on one screen.
- *As a user,* I can generate a briefing and see whether it came from AI or the rule-based engine.
- *As a user,* I can set three priorities for today and mark them done.
- *As a user,* I can press Ctrl+K, type `remind me to call mom tomorrow at 6pm`, see the parsed
  date and confirm.
- *As a user,* I receive a notification when a reminder is due and can snooze it 10 min / 1 h.
- *As a user,* I can add my Google Calendar's ICS address and see those meetings in my agenda.
- *As a user,* I can connect my mailbox with an app password, see unread messages and convert
  one into a task.
- *As a user,* I can switch between today / overdue / upcoming / done task views and edit tasks.

## 7. Key user flows

1. **Onboarding:** Register → land on empty dashboard with guided empty states ("Add your first
   task", "Connect a calendar") → Settings for calendar/email.
2. **Morning routine:** Open dashboard → *Generate briefing* → set priorities from suggestions →
   work through agenda.
3. **Capture:** Ctrl+K → type → preview shows type + parsed date → Enter → toast "Task added".
4. **Reminder fires:** poll finds due reminder → toast + browser notification → Snooze / Done.
5. **Email triage:** Inbox → *Sync* → unread list → *Make task* → task appears with sender + subject.

## 8. Non-functional requirements

- Runs locally with one command after setup; SQLite, no external services required.
- Passwords hashed with scrypt; session cookie HttpOnly + SameSite=Lax; CSRF header check.
- Third-party secrets (IMAP password, private ICS URL) encrypted at rest.
- All API inputs validated; consistent JSON error shape.
- Responsive from 360 px phones to wide desktops; keyboard accessible; light and dark themes.
- Automated tests for API, services and key UI logic; no live AI calls in tests.

## 9. Success criteria

- A new user can register, add a task, a reminder, an event and see all three on the dashboard
  in under two minutes.
- Briefing returns in < 1 s (rule-based) and is labelled with its source.
- All backend and frontend tests pass; the app is verified end-to-end in a browser.
