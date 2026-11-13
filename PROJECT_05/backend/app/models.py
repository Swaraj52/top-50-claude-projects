from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, UTCDateTime, utcnow

HABIT_STATUSES = ("active", "paused", "archived")
LOG_STATUSES = ("done", "skipped")
SOURCES = ("local", "claude")


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


class Habit(Base):
    __tablename__ = "habits"
    __table_args__ = (
        CheckConstraint(f"status IN {HABIT_STATUSES}", name="ck_habits_status"),
        Index("ix_habits_user_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(120))
    intention: Mapped[str] = mapped_column(Text, default="")
    cue: Mapped[str] = mapped_column(String(160), default="")
    # Comma-separated ISO weekdays: 0 = Monday ... 6 = Sunday. At least one.
    days: Mapped[str] = mapped_column(String(20), default="0,1,2,3,4,5,6")
    status: Mapped[str] = mapped_column(String(10), default="active")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    archived_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    logs: Mapped[list["HabitLog"]] = relationship(
        back_populates="habit", cascade="all, delete-orphan", passive_deletes=True
    )
    suggestions: Mapped[list["Suggestion"]] = relationship(
        back_populates="habit", cascade="all, delete-orphan", passive_deletes=True
    )


class HabitLog(Base):
    __tablename__ = "habit_logs"
    __table_args__ = (
        UniqueConstraint("habit_id", "day", name="uq_logs_habit_day"),
        CheckConstraint(f"status IN {LOG_STATUSES}", name="ck_logs_status"),
        Index("ix_logs_user_day", "user_id", "day"),
        Index("ix_logs_habit_day", "habit_id", "day"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    habit_id: Mapped[int] = mapped_column(ForeignKey("habits.id", ondelete="CASCADE"))
    day: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), default="done")
    note: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)

    habit: Mapped[Habit] = relationship(back_populates="logs")


class Reflection(Base):
    __tablename__ = "reflections"
    __table_args__ = (
        UniqueConstraint("user_id", "week_start", name="uq_reflections_user_week"),
        CheckConstraint("mood BETWEEN 1 AND 5", name="ck_reflections_mood"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    week_start: Mapped[date] = mapped_column(Date)
    mood: Mapped[int] = mapped_column(Integer, default=3)
    worked: Mapped[str] = mapped_column(Text, default="")
    friction: Mapped[str] = mapped_column(Text, default="")
    change: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)


class Suggestion(Base):
    __tablename__ = "suggestions"
    __table_args__ = (
        CheckConstraint(f"source IN {SOURCES}", name="ck_suggestions_source"),
        Index("ix_suggestions_habit_created", "habit_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    habit_id: Mapped[int] = mapped_column(ForeignKey("habits.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(140))
    rationale: Mapped[str] = mapped_column(String(400))
    source: Mapped[str] = mapped_column(String(10), default="local")
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)

    habit: Mapped[Habit] = relationship(back_populates="suggestions")
