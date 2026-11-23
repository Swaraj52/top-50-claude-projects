from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
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
REVIEW_LABELS = {1: "Every month", 3: "Every quarter", 6: "Every six months", 12: "Every year"}

RUN_STATUSES = ("open", "done", "abandoned")
RUN_STATUS_LABELS = {"open": "Open", "done": "Done", "abandoned": "Abandoned"}

MAX_STEPS = 40


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


class Person(Base):
    __tablename__ = "people"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_people_user_name"),
        Index("ix_people_user_active", "user_id", "active"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(80), default="")
    email: Mapped[str] = mapped_column(String(254), default="")
    notes: Mapped[str] = mapped_column(String(300), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    sops: Mapped[list["Sop"]] = relationship(back_populates="owner", passive_deletes=True)


class Sop(Base):
    __tablename__ = "sops"
    __table_args__ = (
        UniqueConstraint("user_id", "code", name="uq_sops_user_code"),
        CheckConstraint(f"area IN {AREAS}", name="ck_sops_area"),
        CheckConstraint(f"status IN {SOP_STATUSES}", name="ck_sops_status"),
        CheckConstraint(f"cadence IN {CADENCES}", name="ck_sops_cadence"),
        CheckConstraint("review_months IN (1, 3, 6, 12)", name="ck_sops_review"),
        Index("ix_sops_user_status", "user_id", "status"),
        Index("ix_sops_user_area", "user_id", "area"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(160))
    area: Mapped[str] = mapped_column(String(20), default="operations")
    status: Mapped[str] = mapped_column(String(12), default="draft")
    purpose: Mapped[str] = mapped_column(Text, default="")
    scope: Mapped[str] = mapped_column(Text, default="")
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("people.id", ondelete="SET NULL"), nullable=True, index=True
    )
    cadence: Mapped[str] = mapped_column(String(10), default="monthly")
    review_months: Mapped[int] = mapped_column(Integer, default=6)
    last_reviewed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    owner: Mapped[Person | None] = relationship(back_populates="sops")
    steps: Mapped[list["SopStep"]] = relationship(
        back_populates="sop", cascade="all, delete-orphan", passive_deletes=True
    )
    runs: Mapped[list["Run"]] = relationship(
        back_populates="sop", cascade="all, delete-orphan", passive_deletes=True
    )


class SopStep(Base):
    __tablename__ = "sop_steps"
    __table_args__ = (
        UniqueConstraint("sop_id", "position", name="uq_steps_sop_position"),
        Index("ix_steps_sop", "sop_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sop_id: Mapped[int] = mapped_column(ForeignKey("sops.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(160))
    detail: Mapped[str] = mapped_column(String(600), default="")
    role: Mapped[str] = mapped_column(String(80), default="")
    minutes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    sop: Mapped[Sop] = relationship(back_populates="steps")


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (
        CheckConstraint(f"status IN {RUN_STATUSES}", name="ck_runs_status"),
        Index("ix_runs_sop_status", "sop_id", "status"),
        Index("ix_runs_started", "started_on"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sop_id: Mapped[int] = mapped_column(ForeignKey("sops.id", ondelete="CASCADE"), index=True)
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("people.id", ondelete="SET NULL"), nullable=True, index=True
    )
    started_on: Mapped[date] = mapped_column(Date)
    due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="open")
    notes: Mapped[str] = mapped_column(Text, default="")
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    sop: Mapped[Sop] = relationship(back_populates="runs")
    owner: Mapped[Person | None] = relationship()
    items: Mapped[list["RunItem"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )


class RunItem(Base):
    __tablename__ = "run_items"
    __table_args__ = (
        UniqueConstraint("run_id", "position", name="uq_items_run_position"),
        Index("ix_items_run", "run_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(160))
    detail: Mapped[str] = mapped_column(String(600), default="")
    role: Mapped[str] = mapped_column(String(80), default="")
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    done_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    note: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    run: Mapped[Run] = relationship(back_populates="items")
