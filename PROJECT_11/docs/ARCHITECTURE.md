# Architecture Documentation: Customer Feedback Analyzer

## Project 11 - TOP-50-CLAUDE-PROJECTS

## 1. High-Level Architecture

The Customer Feedback Analyzer follows a server-rendered web application pattern with the following components:

```
┌─────────────────────────┐
│   Client Browser        │
│  (HTMX + Jinja2 templates) │
└─────────────┬─────────────┘
              │  HTMX requests (POST/GET)
              ▼
┌─────────────────────────┐
│   FastAPI Application   │
│  └── Routes (feedback, auth)│
│  ├── Request validation   │
│  ├── DB operations (SQLAlchemy)│
│  ├── Sentiment analysis   │
│  ├── Template rendering   │
│  └── Redirects/Responses │
└─────────────┬─────────────┘
              │
              ▼
┌─────────────────────────┐
│   SQLite Database       │
│  tables: users, sessions, feedback_entries │
└─────────────────────────┘
```

## 2. Component Details

### 2.1 FastAPI Application (`app/main.py`)

- Entry point for the application
- Configures lifespan (database sessionmaker initialization)
- Mounts static files (CSS, JS, favicon)
- Includes routers: `auth` (prefix `/auth`), `feedback` (prefix `/feedback`)
- Favicon endpoint `/favicon.ico`

### 2.2 API Routes

#### 2.2.1 Feedback Routes (`app/routes/feedback.py`)

- `GET /feedback/` - Dashboard page
- `POST /feedback/import` - Import and analyze feedback
- `POST /feedback/analyze` - Sentiment analysis endpoint
- `POST /feedback/pain-points` - Pain points extraction
- `POST /feedback/feature-requests` - Feature requests extraction
- `POST /feedback/list` - List feedback entries
- `POST /feedback/clear` - Clear all feedback

#### 2.2.2 Auth Routes (`app/routes/auth/auth.py`)

- `GET /auth/login` - Login page
- `POST /auth/login` - Process login form
- `GET /auth/register` - Register page
- `POST /auth/register` - Process registration form
- `POST /auth/logout` - Logout and clear session

### 2.3 Database Models (`app/models.py`)

Three main tables:

1. **users**: Stores user authentication data (email, name, password hash, timezone)
2. **sessions**: Stores session tokens and CSRF tokens for authentication
3. **feedback_entries**: Stores feedback reviews with sentiment analysis results
   - `review_text`: The original feedback text
   - `sentiment_theme`: Positive/negative/neutral classification
   - `pain_points`: Extracted pain point keywords
   - `feature_requests`: Extracted feature request keywords

### 2.4 Web Helpers (`app/web.py`)

- `render()`: Render Jinja2 templates with consistent context
- `see_other()`: 303 See Other redirect
- `csrf_token()`: Extract CSRF token from form or cookie
- `pre_csrf()`: CSRF validation dependency
- `ctx()`: Provide template context from session
- `get_db()`: Get database session from app state

### 2.5 Security (`app/security.py`)

- `hash_password()`: PBKDF2 password hashing
- `verify_password()`: Password verification
- `new_session_token()`: Generate random session token
- `hash_token()`: Hash token for secure storage

### 2.6 Time Utilities (`app/timeutil.py`)

- `local_today()`: Get today's date in user's timezone
- `relative_label()`: Calculate relative time labels (e.g., "2 hours ago")
- `zone()`: Create ZoneInfo timezone object

## 3. Data Flow

### 3.1 Feedback Import Flow

1. User submits feedback text via form (`POST /feedback/import`)
2. Form data is parsed (`await request.form()`)
3. Sentiment analysis is performed locally (`_analyze_sentiment()`)
4. Pain points and feature requests are extracted (`_extract_pain_points()`, `_extract_feature_requests()`)
5. FeedbackEntry model is created and saved to database
6. User is redirected to dashboard with success status

### 3.2 Authentication Flow

1. User navigates to `/auth/login` or `/auth/register`
2. Form submission validates email/password (register) or credentials (login)
3. On success, a session is created with token and CSRF token
4. Session cookies (`fd_session`, `fd_csrf`) are set in the browser
5. User is redirected to `/feedback/` dashboard
6. On subsequent requests, `pre_csrf()` validates the CSRF token

### 3.3 Feedback List Flow

1. User visits `/feedback/list` (or clicks "View List" on dashboard)
2. `ctx()` reads session cookies to identify the user
3. Database query fetches feedback entries for the user
4. Template renders the entries in a table
5. User can clear entries or add new feedback

## 4. Dependencies

### 4.1 Python Packages

- `fastapi` - Web framework
- `sqlalchemy` - ORM
- `starlette` - ASGI framework (via FastAPI)
- `jinja2` - Template engine
- `htmxorg` - HTMX library
- `alembic` - Database migrations

### 4.2 Optional Packages

- `anthropic` - Claude AI integration (future)
- `psycopg2` - PostgreSQL support (production)

## 5. Environment Configuration

### 5.1 Environment Variables (.env.example)

```
DEBUG=0
DATABASE_URL=sqlite:///data/foundry.db
SECRET_KEY=foundry-dev-key-change-in-production
AI_ENABLED=false
ANTHROPIC_MODEL=claude-3-opus-20240229
LOG_LEVEL=INFO
SESSION_DAYS=30
```

### 5.2 Directory Structure

```
PROJECT_11/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── security.py
│   │   ├── timeutil.py
│   │   ├── web.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── auth/
│   │   │   │   └── auth.py
│   │   │   └── feedback.py
│   │   ├── static/
│   │   │   ├── feedback.css
│   │   │   └── feedback.js
│   │   └── templates/
│   │       ├── base.html
│   │       ├── feedback_dashboard.html
│   │       └── feedback_list.html
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   │       └── 0001_initial_schema.py
│   ├── alembic.ini
│   ├── tests/
│   │   ├── conftest.py
│   │   └── test_feedback.py
│   └── data/ (created at runtime)
├── docs/
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   └── YOUR_DATA.md
├── README.md
└── launch.json (project configuration)
```

## 6. Database Schema

### 6.1 Entity-Relationship Diagram

```
users {
  id (PK)
  email (unique)
  name
  password_hash
  timezone
  created_at
}

sessions {
  id (PK)
  user_id (FK → users.id)
  token_hash (unique)
  csrf_token (unique)
  expires_at
}

feedback_entries {
  id (PK)
  user_id (FK → users.id)
  review_text
  sentiment_theme
  pain_points
  feature_requests
  created_at
}
```

### 6.2 Alembic Migration (`alembic/versions/0001_initial_schema.py`)

The initial migration creates all three tables with proper foreign key constraints and indexes.

## 7. Testing Strategy

### 6.1 Test Coverage

- Unit tests for sentiment analysis functions
- Unit tests for pain points extraction
- Unit tests for feature requests extraction
- Integration tests for API endpoints
- CSRF token validation tests
- Authentication flow tests

### 6.2 Test Client Setup

Tests use a per-test temporary SQLite database with SQLAlchemy model creation. The TestClient is configured with session and CSRF cookies for authenticated requests.

## 7. Deployment

### 7.1 Development

```bash
cd backend
python run_server.py
# Access at http://127.0.0.1:8011
```

### 7.2 Production

- Use PostgreSQL instead of SQLite
- Set `DEBUG=0` and proper `SECRET_KEY`
- Use a production WSGI/ASGI server (Uvicorn, Gunicorn)
- Configure proper database URL via `DATABASE_URL` environment variable