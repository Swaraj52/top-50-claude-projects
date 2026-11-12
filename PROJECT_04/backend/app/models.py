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

GOAL_CATEGORIES = ("career", "health", "learning", "finance", "personal", "creative")
GOAL_STATUSES = ("active", "achieved", "paused", "archived")
ACTION_STATUSES = ("open", "done", "skipped")
MILESTONE_STATUSES = ("open", "done")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(255))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    weekly_capacity_min: Mapped[int] = mapped_column(Integer, default=300)
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


class Goal(Base):
    __tablename__ = "goals"
    __table_args__ = (
        CheckConstraint(f"category IN {GOAL_CATEGORIES}", name="ck_goals_category"),
        CheckConstraint(f"status IN {GOAL_STATUSES}", name="ck_goals_status"),
        Index("ix_goals_user_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    why: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(20), default="personal")
    status: Mapped[str] = mapped_column(String(10), default="active")
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    achieved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    milestones: Mapped[list["Milestone"]] = relationship(
        back_populates="goal",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Milestone.position, Milestone.id",
    )
    actions: Mapped[list["WeeklyAction"]] = relationship(
        back_populates="goal", cascade="all, delete-orphan", passive_deletes=True
    )
    checkins: Mapped[list["Checkin"]] = relationship(
        back_populates="goal", cascade="all, delete-orphan", passive_deletes=True
    )


class Milestone(Base):
    __tablename__ = "milestones"
    __table_args__ = (
        CheckConstraint(f"status IN {MILESTONE_STATUSES}", name="ck_milestones_status"),
        CheckConstraint("weight BETWEEN 1 AND 5", name="ck_milestones_weight"),
        Index("ix_milestones_goal", "goal_id", "position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(160))
    detail: Mapped[str] = mapped_column(Text, default="")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    weight: Mapped[int] = mapped_column(Integer, default=1)
    position: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(10), default="open")
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    goal: Mapped[Goal] = relationship(back_populates="milestones")


class WeeklyAction(Base):
    __tablename__ = "weekly_actions"
    __table_args__ = (
        CheckConstraint(f"status IN {ACTION_STATUSES}", name="ck_actions_status"),
        CheckConstraint("estimate_min BETWEEN 5 AND 600", name="ck_actions_estimate"),
        CheckConstraint("source IN ('manual','coach')", name="ck_actions_source"),
        Index("ix_actions_user_week", "user_id", "week_start", "status"),
        Index("ix_actions_goal", "goal_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"))
    milestone_id: Mapped[int | None] = mapped_column(
        ForeignKey("milestones.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200))
    estimate_min: Mapped[int] = mapped_column(Integer, default=45)
    week_start: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), default="open")
    source: Mapped[str] = mapped_column(String(10), default="manual")
    done_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    goal: Mapped[Goal] = relationship(back_populates="actions")
    milestone: Mapped[Milestone | None] = relationship()


class Checkin(Base):
    __tablename__ = "checkins"
    __table_args__ = (
        UniqueConstraint("goal_id", "day", name="uq_checkins_goal_day"),
        CheckConstraint("confidence BETWEEN 1 AND 5", name="ck_checkins_confidence"),
        Index("ix_checkins_user_day", "user_id", "day"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"))
    day: Mapped[date] = mapped_column(Date)
    confidence: Mapped[int] = mapped_column(Integer, default=3)
    note: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    goal: Mapped[Goal] = relationship(back_populates="checkins")
