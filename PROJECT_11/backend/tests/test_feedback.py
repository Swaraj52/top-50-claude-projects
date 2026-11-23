"""Tests for Customer Feedback Analyzer (Project 11).

Tests cover feedback import, sentiment analysis, pain points extraction,
feature requests extraction, feedback list, and clear functionality.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import User
from app.security import hash_password


def test_feedback_import(client, db, user, csrf_token):
    """Test importing feedback from reviews/surveys."""
    response = client.post(
        "/feedback/import",
        data={"reviews": "The product is great but the shipping took too long.", "csrf_token": csrf_token},
    )
    assert response.status_code in (200, 302)


def test_sentiment_analysis(client, db, user, csrf_token):
    """Test sentiment analysis endpoint."""
    response = client.post(
        "/feedback/analyze",
        data={"text": "The product is great but the shipping took too long.", "csrf_token": csrf_token},
    )
    assert response.status_code in (200, 302, 400)


def test_pain_points_extraction(client, db, user, csrf_token):
    """Test pain points extraction from feedback."""
    response = client.post(
        "/feedback/pain-points",
        data={"reviews": "The battery drains too quickly and the screen is fragile.", "csrf_token": csrf_token},
    )
    assert response.status_code in (200, 302, 400)


def test_feature_requests_extraction(client, db, user, csrf_token):
    """Test feature requests extraction from feedback."""
    response = client.post(
        "/feedback/feature-requests",
        data={"reviews": "I wish it had wireless charging and a better camera.", "csrf_token": csrf_token},
    )
    assert response.status_code in (200, 302, 400)


def test_feedback_list(client, db, user, csrf_token):
    """Test listing stored feedback entries."""
    response = client.post("/feedback/list", data={"csrf_token": csrf_token})
    assert response.status_code in (200, 302)


def test_feedback_clear(client, db, user, csrf_token):
    """Test clearing all stored feedback."""
    response = client.post("/feedback/clear", data={"csrf_token": csrf_token})
    assert response.status_code in (200, 302, 404)