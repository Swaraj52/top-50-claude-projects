from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, UTCDateTime, utcnow

SOURCES = ("local", "claude")
ACTION_STATUSES = ("open", "done")
DECISION_STATUSES = ("agreed", "revisit")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(255))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)

    user: Mapped[User] = relationship()


class Meeting(Base):
    __tablename__ = "meetings"
    __table_args__ = (
        CheckConstraint(f"source IN {SOURCES}", name="ck_meetings_source"),
        Index("ix_meetings_user_date", "user_id", "occurred_on"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(160))
    occurred_on: Mapped[date] = mapped_column(Date)
    attendees: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(10), default="local")
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    extract_note: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    decisions: Mapped[list["Decision"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan", passive_deletes=True
    )
    actions: Mapped[list["ActionItem"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan", passive_deletes=True
    )


class Decision(Base):
    __tablename__ = "decisions"
    __table_args__ = (
        CheckConstraint(f"status IN {DECISION_STATUSES}", name="ck_decisions_status"),
        Index("ix_decisions_user_date", "user_id", "decided_on"),
        Index("ix_decisions_meeting", "meeting_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="agreed")
    decided_on: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    meeting: Mapped[Meeting] = relationship(back_populates="decisions")


class ActionItem(Base):
    __tablename__ = "action_items"
    __table_args__ = (
        CheckConstraint(f"status IN {ACTION_STATUSES}", name="ck_actions_status"),
        Index("ix_actions_user_status_due", "user_id", "status", "due_date"),
        Index("ix_actions_meeting", "meeting_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(280))
    owner: Mapped[str] = mapped_column(String(80), default="")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="open")
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    meeting: Mapped[Meeting] = relationship(back_populates="actions")
