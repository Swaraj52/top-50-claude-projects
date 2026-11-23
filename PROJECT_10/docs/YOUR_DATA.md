# Foundry - YOUR_DATA.md

This document describes the data stored by Foundry for the business operations hub.

## Data Persistence

All data is stored in a local SQLite database at `data/foundry.db`. The database is created and migrated automatically on first run using Alemcic. No data is transmitted to external services unless explicitly requested via the export feature.

## Tables and Fields

### users
- `id` (INTEGER, PRIMARY KEY)
- `email` (TEXT, UNIQUE, 254 chars max)
- `name` (TEXT, 80 chars max)
- `password_hash` (TEXT, 255 chars)
- `timezone` (TEXT, 64 chars)
- `created_at` (DATETIME)

### sessions
- `id` (INTEGER, PRIMARY KEY)
- `user_id` (INTEGER, FK → users.id, ondelete=CASCADE)
- `token_hash` (TEXT, 64 chars, UNIQUE)
- `csrf_token` (TEXT, 64 chars)
- `created_at` (DATETIME)
- `expires_at` (DATETIME)

### people
- `id` (INTEGER, PRIMARY KEY)
- `user_id` (INTEGER, FK → users.id, ondelete=CASCADE)
- `name` (TEXT, 80 chars)
- `role` (TEXT, 80 chars, default "")
- `email` (TEXT, 254 chars, default "")
- `notes` (TEXT, 300 chars, default "")
- `active` (BOOLEAN, default True)
- `created_at` (DATETIME)

### sops
- `id` (INTEGER, PRIMARY KEY)
- `user_id` (INTEGER, FK → users.id, ondelete=CASCADE)
- `code` (TEXT, 20 chars)
- `title` (TEXT, 160 chars)
- `area` (TEXT, nullable: sales/delivery/finance/people/operations/product)
- `purpose` (TEXT)
- `scope` (TEXT)
- `owner_id` (INTEGER, FK → people.id, ondelete=SET NULL)
- `cadence` (TEXT, nullable: daily/weekly/monthly/quarterly/ad_hoc)
- `review_months` (INTEGER, nullable: 1/3/6/12)
- `last_reviewed_on` (DATE, nullable)
- `version` (INTEGER, default 1)
- Status check: draft/active/retired
- Cadence check: daily/weekly/monthly/quarterly/ad_hoc
- Review months check: 1/3/6/12

### sop_steps
- `id` (INTEGER, PRIMARY KEY)
- `sop_id` (INTEGER, FK → sops.id, ondelete=CASCADE)
- `position` (INTEGER, nullable)
- `title` (TEXT, 160 chars)
- `detail` (TEXT, 600 chars, default "")
- `role` (TEXT, 80 chars, default "")
- `minutes` (INTEGER, default 0)
- `created_at` (DATETIME)

### runs
- `id` (INTEGER, PRIMARY KEY)
- `sop_id` (INTEGER, FK → sops.id, ondelete=CASCADE)
- `owner_id` (INTEGER, FK → people.id, ondelete=SET NULL, nullable)
- `started_on` (DATE, nullable)
- `due_on` (DATE, nullable)
- `status` (TEXT, 12 chars: open/done/abandoned)
- `notes` (TEXT, default "")
- `completed_at` (DATETIME, nullable)
- `created_at` (DATETIME)

### run_items
- `id` (INTEGER, PRIMARY KEY)
- `run_id` (INTEGER, FK → runs.id, ondelete=CASCADE)
- `position` (INTEGER, nullable)
- `title` (TEXT, 160 chars)
- `detail` (TEXT, 600 chars, default "")
- `role` (TEXT, 80 chars, default "")
- `done` (BOOLEAN, default False)
- `done_at` (DATETIME, nullable)
- `note` (TEXT, 300 chars, default "")
- `created_at` (DATETIME)

## Data Privacy

- **All data local**: Nothing leaves the user's machine unless explicitly exported
- **No analytics**: No tracking, no remote logging
- **No backups to cloud**: Database file stays in `data/` directory
- **Export optional**: `foundry-export-v1` JSON export is user-initiated only

## What Data Is Stored About You

When you use Foundry, the following data is stored in your database:
- Your user account (email, name, timezone)
- Your SOPs and their configuration
- People tracked in your organization
- Runs and checklist progress
- Your settings (name, timezone, password hash)

## Export Format

The `foundry-export-v1` format includes:
- People: name, role, email, notes, active status
- SOPs: code, title, area, purpose, scope, owner, cadence, review_months, last_reviewed_on, version, steps
- Runs: sop_code, owner, started_on, due_on, status, notes, items
- Items: position, title, detail, role, done, done_at, note

## Recovery

If the database file `data/foundry.db` is lost, re-running the application will recreate it from the Alembic migration. Any data not in the database will be lost. The export feature can be used to back up data before running migrations.