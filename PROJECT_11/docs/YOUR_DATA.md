# Your Data: Customer Feedback Analyzer

## Project 11 - TOP-50-CLAUDE-PROJECTS

## 1. Database Structure

Your feedback data is stored in a SQLite database at `backend/data/foundry.db` (development) or configured via `DATABASE_URL` environment variable.

### 1.1 Tables

#### users
| Column | Type | Description |
|---|---|---|
| id | INTEGER | Primary key |
| email | STRING(254) | Unique user email |
| name | STRING(80) | User's display name |
| password_hash | STRING(255) | Hashed password (PBKDF2) |
| timezone | STRING(64) | User's timezone (default: UTC) |
| created_at | DATETIME | Account creation timestamp |

#### sessions
| Column | Type | Description |
|---|---|---|
| id | INTEGER | Primary key |
| user_id | INTEGER | Foreign key to users.id |
| token_hash | STRING(128) | Hashed session token (unique) |
| csrf_token | STRING(128) | CSRF token (unique) |
| expires_at | DATETIME | Session expiration time |

#### feedback_entries
| Column | Type | Description |
|---|---|---|
| id | INTEGER | Primary key |
| user_id | INTEGER | Foreign key to users.id |
| review_text | TEXT | The original feedback text |
| sentiment_theme | STRING(100) | Sentiment classification (positive/negative/neutral) |
| pain_points | TEXT | Semicolon-separated list of identified pain points |
| feature_requests | TEXT | Semicolon-separated list of feature requests |
| created_at | DATETIME | When the feedback was imported |

### 1.2 Example Data

#### users table:

| id | email | name | password_hash | timezone | created_at |
|---|---|---|---|---|---|
| 1 | demo@foundry.example | demo | *hashed* | UTC | 2026-11-24 |

#### feedback_entries table:

| id | user_id | review_text | sentiment_theme | pain_points | feature_requests | created_at |
|---|---|---|---|---|---|---|
| 1 | 1 | "The product is great but the shipping took too long." | positive | "problem; issue" | "wish; feature" | 2026-11-24 |

### 1.3 Data Seeding

The application includes a demo account for testing:
- **Email**: `demo@foundry.example`
- **Password**: `demo-password`
- **One SOP**: OPS-01 with 4 steps (Foundry-specific, Project 10 data)

### 1.4 Backing Up Your Data

The database file is located at `backend/data/foundry.db`. To back up your data:
1. Copy the `backend/data/foundry.db` file
2. Store it in a safe location
3. To restore, copy the file back to the same location

### 1.5 Data Migration

If you need to migrate to a new database or change the URL:
1. Update `DATABASE_URL` in `.env.example` or environment variables
2. Create a new Alembic migration: `alembic revision --head`
3. Run migrations: `alembic upgrade head`
4. Verify data integrity

## 2. Sample Records

### 2.1 Importing Your First Feedback

When you first import feedback, the system:

1. Creates a user account (or uses existing session)
2. Saves the review text to `feedback_entries.review_text`
3. Analyzes sentiment and stores `sentiment_theme`
4. Extracts pain points and stores `pain_points`
5. Extracts feature requests and stores `feature_requests`
6. Sets `created_at` to the current timestamp

### 2.2 Viewing Your Data

Feedback entries can be viewed via:
- The dashboard page (`/feedback/`)
- The list page (`/feedback/list`)
- Direct database queries using SQLAlchemy or SQL

### 2.3 Clearing Your Data

The clear function (`POST /feedback/clear`) deletes all feedback entries for the authenticated user from the `feedback_entries` table. This action is irreversible.

## 3. Configuration

### 3.1 Database URL

The default database URL is `sqlite:///data/foundry.db`. To use a different database:

```bash
export DATABASE_URL="postgresql://user:password@host:port/database"
```

Update `.env.example` or set the environment variable before running the application.

### 3.2 Customizing Analysis

The local sentiment analysis uses keyword-based patterns. To customize:

- Modify `positive_words` and `negative_words` in `app/routes/feedback.py`
- Modify `pain_keywords` and `feature_keywords` in `app/routes/feedback.py`
- Add AI-powered analysis (future enhancement)

## 4. Privacy

- Feedback text is stored locally in the database
- No data is sent to external services (sentiment analysis is local only)
- Passwords are hashed with PBKDF2 and never stored in plain text
- Session tokens are hashed for security