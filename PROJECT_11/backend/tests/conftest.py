"""Conftest for Customer Feedback Analyzer (Project 11).

Provides a per-test temporary SQLite database, with tables created via SQLAlchemy.
"""

from __future__ import annotations

import json
import os
import random
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select

# Add the backend directory to the path so we can import app modules
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


from app.config import Settings
from app.db import make_engine, make_sessionmaker, utcnow, Base
from app.main import create_app
from app.models import User, Session


def _make_email(base: str = "test") -> str:
    """Generate a unique email per test using a random suffix."""
    import string
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{base}_{suffix}@example.com"


@pytest.fixture(scope="function")
def db():
    """Create a fresh database per test, with tables created via SQLAlchemy."""
    test_db = f"./test_{os.getpid()}_{random.randint(1000, 9999)}.db"
    engine = create_engine(f"sqlite:///{test_db}", echo=False)
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    session_factory = make_sessionmaker(engine)
    
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()
        if os.path.exists(test_db):
            try:
                os.remove(test_db)
            except PermissionError:
                pass


@pytest.fixture(scope="function")
def user(db):
    """Create a test user in the database."""
    from app.models import User
    from app.security import hash_password

    user = User(
        email=_make_email("user"),
        name="Test User",
        password_hash=hash_password("password123"),
        timezone="UTC",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture(scope="function")
def client(db, user):
    """Create a TestClient with the app and a session for the given user."""
    from app.models import Session
    import secrets

    app = create_app(Settings(database_url=f"sqlite:///{db.bind.url.database}"))

    # Create a session with CSRF token
    csrf_token_val = secrets.token_urlsafe(32)
    session = Session(
        user_id=user.id,
        token_hash=csrf_token_val,
        csrf_token=csrf_token_val,
        expires_at=utcnow() + timedelta(days=30),
    )
    db.add(session)
    db.commit()

    # Create test client with cookies
    client = TestClient(app)
    # Set both session and CSRF cookies - pre_csrf checks fd_csrf cookie
    client.cookies.set("fd_session", csrf_token_val)
    client.cookies.set("fd_csrf", csrf_token_val)

    yield client

    # Cleanup
    client.cookies.delete("fd_session")
    client.cookies.delete("fd_csrf")


@pytest.fixture(scope="function")
def csrf_token(client, db, user):
    """Provide the CSRF token from the current session for use in form submissions."""
    # Read the CSRF token from the session in the database
    session = db.scalar(select(Session).where(Session.user_id == user.id))
    if session is None:
        # Generate a token if session not found
        csrf_token_val = secrets.token_urlsafe(32)
        return csrf_token_val
    return session.csrf_token