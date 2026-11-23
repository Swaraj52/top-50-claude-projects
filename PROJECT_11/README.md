# Customer Feedback Analyzer

**Project 11 of TOP-50-CLAUDE-PROJECTS**

> Pulls recurring themes and product opportunities out of reviews, surveys and support feedback.

## Built by Swayam

![Built by Swayam](https://img.shields.io/badge/built%20by%20Swayam-%233b82f6.svg)

## Overview

The Customer Feedback Analyzer helps organizations make sense of customer feedback by providing:

- **Sentiment analysis** - Determine if feedback is positive, negative, or neutral
- **Pain points extraction** - Identify recurring problems and issues mentioned in feedback
- **Feature requests extraction** - Extract feature wishes and improvement suggestions

## Features

- Sentiment themes (positive/negative/neutral)
- Pain points keyword extraction
- Feature requests keyword extraction
- Feedback import and storage
- Feedback list and clear functionality

## Tech Stack

- FastAPI - Web framework
- SQLAlchemy - ORM for database operations
- SQLite - Database (development/testing)
- HTMX - Interactive UI enhancements
- Alembic - Database migration

## Screenshots

![Feedback Dashboard - Light Mode](screenshots/feedback-dashboard-light.png)
![Feedback Dashboard - Dark Mode](screenshots/feedback-dashboard-dark.png)
![Feedback List - Mobile](screenshots/feedback-list-mobile.png)

## Available Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/feedback/` | GET | Feedback dashboard page |
| `/feedback/import` | POST | Import and analyze feedback |
| `/feedback/analyze` | POST | Analyze sentiment of feedback text |
| `/feedback/pain-points` | POST | Extract pain points from feedback |
| `/feedback/feature-requests` | POST | Extract feature requests from feedback |
| `/feedback/list` | POST | List stored feedback entries |
| `/feedback/clear` | POST | Clear all stored feedback |
| `/auth/login` | GET/POST | Login page and authentication |
| `/auth/register` | GET/POST | Register new user |
| `/auth/logout` | POST | Logout and clear session |

## Development

```bash
# Install dependencies
cd backend
pip install -r requirements.txt

# Run the server
python run_server.py

# Access at http://127.0.0.1:8011
```