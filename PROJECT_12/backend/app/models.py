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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, utcnow


class User(Base):
    """User model for authentication."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)


class Session(Base):
    """Session model for authentication."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    csrf_token: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)


class Competitor(Base):
    """Competitor model for competitor research dashboard."""

    __tablename__ = "competitors"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(254), nullable=False)
    website: Mapped[str] = mapped_column(String(512), nullable=True)
    positioning: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="competitors")
    comparisons: Mapped[list["Comparison"]] = relationship(
        back_populates="competitor", cascade="all, delete-orphan"
    )
    opportunities: Mapped[list["OpportunityNote"]] = relationship(
        back_populates="competitor", cascade="all, delete-orphan"
    )


class Comparison(Base):
    """Comparison model for competitor metrics."""

    __tablename__ = "comparisons"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    competitor_id: Mapped[int] = mapped_column(
        ForeignKey("competitors.id"), nullable=False
    )
    metric: Mapped[str] = mapped_column(String(200), nullable=False)
    score: Mapped[float] = mapped_column(nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=utcnow
    )

    # Relationships
    competitor: Mapped["Competitor"] = relationship(back_populates="comparisons")


class OpportunityNote(Base):
    """Opportunity note model for competitor analysis."""

    __tablename__ = "opportunity_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    competitor_id: Mapped[int] = mapped_column(
        ForeignKey("competitors.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=utcnow
    )

    # Relationships
    competitor: Mapped["Competitor"] = relationship(back_populates="opportunities")