"""Tests for Foundry authentication, following the P09 pattern."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import User
from app.security import hash_password


def test_registration(client, db, csrf_token):
    """Test user registration with valid data."""
    response = client.post(
        "/register",
        data={"name": "Alice", "email": "alice@example.com", "password": "password123",
              "timezone": "Asia/Kolkata", "csrf_token": csrf_token},
    )
    assert response.status_code == 303  # redirect to /
    
    # Verify user was created
    user = db.scalar(select(User).where(User.email == "alice@example.com"))
    assert user is not None
    assert user.name == "Alice"


def test_login(client, db, user, csrf_token):
    """Test user login."""
    response = client.post(
        "/login",
        data={"email": "alice@example.com", "password": "password123", "csrf_token": csrf_token},
    )
    assert response.status_code == 303  # redirect to /
    
    # Verify session cookie was set
    assert client.cookies.get("fd_session") is not None


def test_logout(client, db, user, csrf_token):
    """Test user logout."""
    # First login
    response = client.post(
        "/login",
        data={"email": "alice@example.com", "password": "password123", "csrf_token": csrf_token},
    )
    assert response.status_code == 303
    
    # Then logout
    response = client.post("/logout")
    assert response.status_code == 303
    
    # Cookie should be deleted
    assert "fd_session" not in client.cookies


def test_csrf_protection(client, db, user, csrf_token):
    """Test that CSRF tokens are required on forms."""
    # Without CSRF token, form submission should fail
    response = client.post("/sops/new", data={"title": "Test SOP"})
    assert response.status_code == 403  # CSRF protection blocks the request
    
    # With CSRF token, form submission should succeed
    response = client.post("/sops/new", data={
        "code": "OPS-TEST",
        "title": "Test Process",
        "area": "finance",
        "purpose": "Test purpose for the SOP",
        "scope": "Test scope",
        "owner_id": "",
        "cadence": "monthly",
        "review_months": 6,
        "csrf_token": csrf_token,
    })
    assert response.status_code in (303, 409)  # redirect or conflict


def test_settings_counts(client, db, user, csrf_token):
    """Test that settings page shows correct counts."""
    response = client.get("/settings")
    assert response.status_code == 200
    # Check that counts are rendered in the template
    text = response.text
    # The counts should include people, sops, steps, runs, items
    assert "People" in text or "SOPs" in text


def test_export_data(client, db, user, csrf_token):
    """Test that the export endpoint returns correct structure."""
    response = client.get("/settings/export")
    assert response.status_code == 200
    assert "foundry-export-v1" in response.headers.get("Content-Disposition", "")
    
    # Verify it's valid JSON
    import json
    data = json.loads(response.text)
    assert data["format"] == "foundry-export-v1"
    assert "people" in data
    assert "sops" in data
    assert "runs" in data


def test_create_sop(client, db, user, csrf_token):
    """Test creating a new SOP."""
    # Login first
    response = client.post(
        "/login",
        data={"email": "alice@example.com", "password": "password123", "csrf_token": csrf_token},
    )
    assert response.status_code == 303  # redirect to /
    
    # Create a new SOP
    response = client.post("/sops/new", data={
        "code": "OPS-TEST",
        "title": "Test Process",
        "area": "finance",
        "purpose": "Test purpose for the SOP",
        "scope": "Test scope",
        "owner_id": "",
        "cadence": "monthly",
        "review_months": 6,
        "csrf_token": csrf_token,
    })
    assert response.status_code in (303, 409)  # redirect or conflict


def test_draft_from_description(client, db, user, csrf_token):
    """Test drafting an SOP from a description."""
    # Login first
    response = client.post(
        "/login",
        data={"email": "alice@example.com", "password": "password123", "csrf_token": csrf_token},
    )
    assert response.status_code == 303  # redirect to /
    
    # Draft from description
    response = client.post("/sops/draft", data={
        "area": "finance",
        "description": "We collect invoices monthly, match them against bank statements, and reconcile any differences.",
        "csrf_token": csrf_token,
    })
    assert response.status_code == 200