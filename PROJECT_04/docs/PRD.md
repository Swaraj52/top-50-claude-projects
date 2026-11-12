# PRD: Personal Goal Tracker (Project 04), "Summit"

## 1. Problem

Long-term goals fail in the gap between the goal and the week. A deadline months away creates no
useful pressure, milestone lists become decoration, and a missed week is easy to hide from
yourself. Most trackers reduce a rich goal to a percentage that nobody trusts, and they ask for
daily logging without ever telling you what to do next.

People need three things in one place:

1. A small set of visible checkpoints, weighted by what actually matters.
2. A realistic plan for *this* week, not a fantasy plan for the whole goal.
3. An honest signal about whether confidence and pace are improving or slipping.

## 2. Target users

Students, individual contributors, freelancers and anyone running two to six personal goals at
once (career, health, learning, finance, personal, creative). They want a private, self-hosted tool
with no subscription, and they are comfortable adding their own milestones.

## 3. Use cases

1. Turn "get fit" into four milestones and see weighted progress rather than a vague checklist.
2. At the start of a week, ask the coach for 3–5 actions and file the useful ones into this week.
3. During the week, tick actions done from the dashboard or the weekly plan.
4. At the end of a hard day, record confidence 1–5 and one sentence about what is in the way.
5. Notice that a goal is behind its straight-line pace and cut scope before the deadline.
6. Browse eight weeks of completion, confidence and category balance.
7. Print a one-page review of a goal for a mentor or accountability partner.
8. Export everything as JSON or delete the account without leftovers.

## 4. MVP scope

| Area | Feature |
|---|---|
| Accounts | Register / sign in / sign out, private data, per-user IANA timezone and weekly capacity |
| Goals | Create, edit, delete, pause, achieve, archive; category, target date, description and "why" |
| Milestones | 1–5 weight, optional due date, detail, add/toggle/delete; weighted progress |
| Pace | Actual vs expected progress from creation date to target date; ahead / on track / behind / overdue / setup / no date |
| Dashboard | Active goals, average progress, done this week, planned minutes vs capacity, check-in streak, at-risk list, six-week momentum |
| Weekly plan | Actions with goal, optional milestone and estimate; toggle with HTMX; delete; previous/next week; carry unfinished actions without duplicates |
| Check-ins | Confidence 1–5 plus a note, one per goal per day, with a streak |
| Coach | 3–5 actions for the current week from Claude when configured, otherwise the labelled local planner; validated and rate-limited |
| Insights | Eight-week completion volume and rate, weekly confidence line, category portfolio, goal-health table |
| Review | Printable one-goal page with state, pace, milestones, this week's actions and recent check-ins |
| Settings | Name, timezone, weekly capacity, password change, JSON export, account deletion |

## 5. Advanced features (post-MVP)

- Calendar-aware scheduling of weekly actions into real free slots
- Weekly review email generated from insights and check-ins
- Recurring actions and habit streaks
- Sub-goals and milestone dependencies
- Import from Notion, Todoist or Markdown
- Shareable read-only progress page

## 6. Out of scope

Team workspaces, social feeds, mobile apps, push notifications, payments, public deployment.

## 7. User stories

- *As a user,* I can turn a goal into four weighted milestones instead of a vague checklist.
- *As a user,* I can see that I am 22% done but 73% of the time has passed, and act on that.
- *As a user,* on Monday I get five concrete actions for this week without planning from scratch.
- *As a user,* I can tick an action done from the dashboard without losing my place.
- *As a user,* I can carry last week's unfinished actions forward without creating duplicates.
- *As a user,* I can record that confidence dropped to 2/5 and see the note in the history.
- *As a user,* I can see which category is moving and which goal has no next milestone.
- *As a user,* I can print a clean one-page review for a mentor.
- *As a user,* I can export my data and delete my account completely.

## 8. Key flows

1. **Set up a goal:** Goals → New goal → title, category, target date, why → add 3–5 milestones
   with weights and due dates.
2. **Plan a week:** This week → add actions (or open a goal → Generate a plan) → review the
   suggested actions → adjust the list.
3. **Work the week:** Dashboard or This week → tick actions done. HTMX swaps the row in place;
   without JavaScript the form posts and redirects.
4. **Check in:** Goal detail → confidence 1–5 → one sentence → Save. Saving again updates today.
5. **Reflect:** Insights → eight-week volume, completion rate, confidence, category balance and
   goal health. Open a goal review for the printable version.
6. **Recover a missed week:** This week → choose the previous week → Carry unfinished actions into
   this week.

## 9. Non-functional requirements

- Single Python process, SQLite, no JavaScript build; forms degrade to full page loads.
- Session cookie + synchronizer CSRF token for every unsafe request.
- AI optional, labelled, and never presented as AI-written unless the API call succeeded.
- All charts are server-rendered: HTML/CSS bars with text values and an SVG line with a text
  alternative and per-point titles.
- Responsive from 390 px to desktop; light-first with a dark variant via `prefers-color-scheme`.
- Per-user isolation on every query; no cross-account reads or writes.
- Tests never call a paid API.

## 10. Success criteria

- A new user can go from an empty account to a first weekly plan in under five minutes.
- Weighted progress, pace and the at-risk list agree with the underlying milestones.
- The coach never invents a goal or milestone that does not exist, and never exceeds the
  week's action list without the user's ability to edit it.
- Carry-over never duplicates an action title in the destination week.
- Eight-week charts are computed in the user's local timezone and stay correct across DST.
- Every screenshot in the docs is reproducible from the seeded demo account.
