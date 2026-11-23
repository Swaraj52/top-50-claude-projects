from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    DateTime,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, utcnow


AREAS = ("sales", "delivery", "finance", "people", "operations", "product")
AREA_LABELS = {
    "sales": "Sales",
    "delivery": "Delivery",
    "finance": "Finance",
    "people": "People",
    "operations": "Operations",
    "product": "Product",
}

SOP_STATUSES = ("draft", "active", "retired")
SOP_STATUS_LABELS = {"draft": "Draft", "active": "Active", "retired": "Retired"}

CADENCES = ("daily", "weekly", "monthly", "quarterly", "ad_hoc")
CADENCE_LABELS = {
    "daily": "Daily",
    "weekly": "Weekly",
    "monthly": "Monthly",
    "quarterly": "Quarterly",
    "ad_hoc": "Ad hoc",
}

REVIEW_MONTHS = (1, 3, 6, 12)
REVIEW_LABELS = {1: "Every month", 3: "Every 3 months", 6: "Every 6 months", 12: "Every year"}


class User(Base):
    """User model for authentication."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class FeedbackEntry(Base):
    """Feedback entry model for customer feedback analyzer."""

    __tablename__ = "feedback_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    review_text: Mapped[str] = mapped_column(Text, nullable=False)
    sentiment_theme: Mapped[str] = mapped_column(String(100), nullable=True)
    pain_points: Mapped[str] = mapped_column(Text, nullable=True)
    feature_requests: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class Session(Base):
    """Session model for authentication."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    csrf_token: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)