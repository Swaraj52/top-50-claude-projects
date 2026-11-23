# Foundry - Product Requirements Document

## Product Name
Foundry: Business Operations Hub

## Target Audience
Small to medium teams needing to manage SOPs, process checklists, and ownership tracking without external dependencies or paid services.

## Problem Statement
Teams need a way to document and track SOPs, assign ownership, and monitor process execution without relying on expensive tools or external services. Existing solutions often require internet access, paid subscriptions, or complex setup.

## Solution
Foundry is a local-first desktop application that runs entirely on the user's machine. It uses SQLite for persistence, FastAPI for the backend, and Jinja2/HTMX for the frontend. All data stays on the user's machine.

## Features

### 1. SOP Library
- Create SOPs with unique codes within a user's scope
- Assign area (sales, delivery, finance, people, operations, product)
- Define purpose, scope, owner, cadence (daily/weekly/monthly/quarterly/ad_hoc)
- Set review cycle (1, 3, 6, 12 months)
- Versioned steps with position, title, detail, role, and estimated minutes
- Status tracking (draft, active, retired)

### 2. Process Checklists
- Start runs from any SOP
- Assign run owner from tracked people
- Set start date and due date
- Track status (open, done, abandoned)
- Checklist items auto-snapshot from SOP steps
- Progress tracking: how many items done, overdue detection
- Abandon runs if needed

### 3. Ownership Dashboard
- Track people: name, role, email, active status
- Area×person coverage matrix: which areas have people assigned
- Unowned list: SOPs without owners
- Dashboard showing next moves across all SOPs and runs

### 4. Optional SOP Drafting
- Generate a starter SOP outline from a free-text description
- Local baseline: structured outline with placeholder steps
- Optional Claude API integration for description-to-SOP transformation (disabled by default, no key required)
- Bounded output: only uses defined areas, cadences, review months

### 4. Export & Import
- Export SOPs, steps, runs, and items as JSON in `foundry-export-v1` format
- Idempotent import: second run skips all items already in the database
- Export structure includes people, sops with steps, runs with items

## Technical Constraints

- **Free-only**: No paid APIs, no Claude credits, no external services
- **Local-only**: All data in SQLite, no cloud sync by default
- **No secrets**: No API keys, tokens, or credentials committed
- **Python 3.13**: Tested on Python 3.13.7
- **No force-push**: Git operations are read-only or safe
- **No destructive actions**: Against unrelated work

## User Stories

1. As a team member, I can create SOPs with codes and assign them to areas
2. As a team member, I can start a checklist run from an SOP and track progress
3. As a team lead, I can see ownership coverage and identify unowned SOPs
4. As a team member, I can export my SOPs and import them elsewhere
5. As a team member, I can optionally generate SOP drafts from descriptions

## Success Metrics

- All 50 projects built and tested sequentially
- Project 10 (Foundry) has working UI, auth, persistence, and exports
- All tests pass (target ~250+ across all projects)
- No paid services or credits used
- No secrets committed to version control