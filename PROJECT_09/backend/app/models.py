from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, UTCDateTime, utcnow

STAGES = ("idea", "validating", "building", "growing")
STAGE_LABELS = {
    "idea": "Idea",
    "validating": "Validating",
    "building": "Building",
    "growing": "Growing",
}

HORIZONS = ("90 days", "6 months", "12 months", "3 years")
CURRENCIES = ("INR", "USD", "EUR", "GBP")
CURRENCY_SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}

CANVAS_BLOCKS = (
    "problem",
    "customers",
    "value",
    "solution",
    "channels",
    "revenue",
    "costs",
    "metrics",
    "advantage",
)
CANVAS_LABELS = {
    "problem": "Problem",
    "customers": "Customer segments",
    "value": "Value proposition",
    "solution": "Solution",
    "channels": "Channels",
    "revenue": "Revenue",
    "costs": "Cost structure",
    "metrics": "Key metrics",
    "advantage": "Unfair advantage",
}
CANVAS_PROMPTS = {
    "problem": "Which concrete problem are you solving, and how do people cope today?",
    "customers": "Who feels the problem most sharply? Name a segment, not everyone.",
    "value": "What changes for that customer in one sentence they would repeat?",
    "solution": "What do you actually build or do, and what is the smallest useful version?",
    "channels": "How will the first hundred customers hear about you?",
    "revenue": "Who pays, for what, and how often?",
    "costs": "What does it cost to serve one customer, and what is fixed?",
    "metrics": "Which three numbers would tell you this is working?",
    "advantage": "What gets harder to copy the longer you run?",
}

QUADRANTS = ("strength", "weakness", "opportunity", "threat")
QUADRANT_LABELS = {
    "strength": "Strength",
    "weakness": "Weakness",
    "opportunity": "Opportunity",
    "threat": "Threat",
}
QUADRANT_HELP = {
    "strength": "What you already have: skills, access, assets, proof.",
    "weakness": "What is missing or fragile inside the business.",
    "opportunity": "What is changing outside that you can reach first.",
    "threat": "What could take the market away, and how soon.",
}

REVENUE_MODELS = ("subscription", "usage", "one_off", "marketplace", "licence")
REVENUE_MODEL_LABELS = {
    "subscription": "Subscription",
    "usage": "Usage-based",
    "one_off": "One-off sale",
    "marketplace": "Marketplace fee",
    "licence": "Licence",
}
CONFIDENCE_LEVELS = ("high", "medium", "low")
CONFIDENCE_LABELS = {"high": "High", "medium": "Medium", "low": "Low"}
CONFIDENCE_WEIGHTS = {"high": 1.0, "medium": 0.7, "low": 0.4}

COST_KINDS = ("fixed", "variable")
COST_KIND_LABELS = {"fixed": "Fixed", "variable": "Variable"}

MILESTONE_HORIZONS = ("now", "next", "later")
MILESTONE_HORIZON_LABELS = {"now": "Now", "next": "Next", "later": "Later"}
MILESTONE_STATUSES = ("planned", "in_progress", "done", "at_risk")
MILESTONE_STATUS_LABELS = {
    "planned": "Planned",
    "in_progress": "In progress",
    "done": "Done",
    "at_risk": "At risk",
}

DIRECTIONS = ("up", "down")
DIRECTION_LABELS = {"up": "Higher is better", "down": "Lower is better"}
CADENCES = ("weekly", "monthly", "quarterly")
CADENCE_LABELS = {"weekly": "Weekly", "monthly": "Monthly", "quarterly": "Quarterly"}


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


class Venture(Base):
    __tablename__ = "ventures"
    __table_args__ = (
        CheckConstraint(f"stage IN {STAGES}", name="ck_ventures_stage"),
        CheckConstraint(f"currency IN {CURRENCIES}", name="ck_ventures_currency"),
        UniqueConstraint("user_id", "name", name="uq_ventures_user_name"),
        Index("ix_ventures_user_updated", "user_id", "updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    one_liner: Mapped[str] = mapped_column(String(240), default="")
    stage: Mapped[str] = mapped_column(String(16), default="idea")
    horizon: Mapped[str] = mapped_column(String(16), default="90 days")
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    market: Mapped[str] = mapped_column(Text, default="")
    segment: Mapped[str] = mapped_column(String(240), default="")
    alternatives: Mapped[str] = mapped_column(Text, default="")
    differentiation: Mapped[str] = mapped_column(Text, default="")
    narrative: Mapped[str] = mapped_column(Text, default="")
    narrative_source: Mapped[str] = mapped_column(String(8), default="local")
    narrative_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    canvas: Mapped[list["CanvasEntry"]] = relationship(
        back_populates="venture", cascade="all, delete-orphan", passive_deletes=True
    )
    swot: Mapped[list["SwotItem"]] = relationship(
        back_populates="venture", cascade="all, delete-orphan", passive_deletes=True
    )
    streams: Mapped[list["RevenueStream"]] = relationship(
        back_populates="venture", cascade="all, delete-orphan", passive_deletes=True
    )
    costs: Mapped[list["CostLine"]] = relationship(
        back_populates="venture", cascade="all, delete-orphan", passive_deletes=True
    )
    milestones: Mapped[list["Milestone"]] = relationship(
        back_populates="venture", cascade="all, delete-orphan", passive_deletes=True
    )
    kpis: Mapped[list["Kpi"]] = relationship(
        back_populates="venture", cascade="all, delete-orphan", passive_deletes=True
    )


class CanvasEntry(Base):
    __tablename__ = "canvas_entries"
    __table_args__ = (
        CheckConstraint(f"block IN {CANVAS_BLOCKS}", name="ck_canvas_block"),
        Index("ix_canvas_venture_block", "venture_id", "block"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    venture_id: Mapped[int] = mapped_column(ForeignKey("ventures.id", ondelete="CASCADE"))
    block: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(160))
    detail: Mapped[str] = mapped_column(String(600), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    venture: Mapped[Venture] = relationship(back_populates="canvas")


class SwotItem(Base):
    __tablename__ = "swot_items"
    __table_args__ = (
        CheckConstraint(f"quadrant IN {QUADRANTS}", name="ck_swot_quadrant"),
        CheckConstraint("impact BETWEEN 1 AND 5", name="ck_swot_impact"),
        Index("ix_swot_venture_quadrant", "venture_id", "quadrant"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    venture_id: Mapped[int] = mapped_column(ForeignKey("ventures.id", ondelete="CASCADE"))
    quadrant: Mapped[str] = mapped_column(String(12))
    text: Mapped[str] = mapped_column(String(300))
    impact: Mapped[int] = mapped_column(Integer, default=3)
    evidence: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    venture: Mapped[Venture] = relationship(back_populates="swot")


class RevenueStream(Base):
    __tablename__ = "revenue_streams"
    __table_args__ = (
        CheckConstraint(f"model IN {REVENUE_MODELS}", name="ck_streams_model"),
        CheckConstraint(f"confidence IN {CONFIDENCE_LEVELS}", name="ck_streams_confidence"),
        CheckConstraint("price >= 0", name="ck_streams_price"),
        CheckConstraint("volume >= 0", name="ck_streams_volume"),
        Index("ix_streams_venture", "venture_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    venture_id: Mapped[int] = mapped_column(ForeignKey("ventures.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    model: Mapped[str] = mapped_column(String(16), default="subscription")
    price: Mapped[int] = mapped_column(Integer, default=0)
    unit: Mapped[str] = mapped_column(String(60), default="per month")
    volume: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[str] = mapped_column(String(8), default="medium")
    notes: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    venture: Mapped[Venture] = relationship(back_populates="streams")


class CostLine(Base):
    __tablename__ = "cost_lines"
    __table_args__ = (
        CheckConstraint(f"kind IN {COST_KINDS}", name="ck_costs_kind"),
        CheckConstraint("amount >= 0", name="ck_costs_amount"),
        Index("ix_costs_venture", "venture_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    venture_id: Mapped[int] = mapped_column(ForeignKey("ventures.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    amount: Mapped[int] = mapped_column(Integer, default=0)
    kind: Mapped[str] = mapped_column(String(10), default="fixed")
    notes: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    venture: Mapped[Venture] = relationship(back_populates="costs")


class Milestone(Base):
    __tablename__ = "milestones"
    __table_args__ = (
        CheckConstraint(f"horizon IN {MILESTONE_HORIZONS}", name="ck_milestones_horizon"),
        CheckConstraint(f"status IN {MILESTONE_STATUSES}", name="ck_milestones_status"),
        Index("ix_milestones_venture_due", "venture_id", "due_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    venture_id: Mapped[int] = mapped_column(ForeignKey("ventures.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(160))
    success_criterion: Mapped[str] = mapped_column(String(300), default="")
    owner: Mapped[str] = mapped_column(String(80), default="")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    horizon: Mapped[str] = mapped_column(String(10), default="now")
    status: Mapped[str] = mapped_column(String(12), default="planned")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    venture: Mapped[Venture] = relationship(back_populates="milestones")


class Kpi(Base):
    __tablename__ = "kpis"
    __table_args__ = (
        CheckConstraint(f"direction IN {DIRECTIONS}", name="ck_kpis_direction"),
        CheckConstraint(f"cadence IN {CADENCES}", name="ck_kpis_cadence"),
        Index("ix_kpis_venture", "venture_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    venture_id: Mapped[int] = mapped_column(ForeignKey("ventures.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    unit: Mapped[str] = mapped_column(String(40), default="")
    direction: Mapped[str] = mapped_column(String(4), default="up")
    baseline: Mapped[float] = mapped_column(Float, default=0.0)
    target: Mapped[float] = mapped_column(Float, default=0.0)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cadence: Mapped[str] = mapped_column(String(10), default="monthly")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    venture: Mapped[Venture] = relationship(back_populates="kpis")
    readings: Mapped[list["KpiReading"]] = relationship(
        back_populates="kpi", cascade="all, delete-orphan", passive_deletes=True
    )


class KpiReading(Base):
    __tablename__ = "kpi_readings"
    __table_args__ = (UniqueConstraint("kpi_id", "recorded_on", name="uq_readings_kpi_day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kpi_id: Mapped[int] = mapped_column(ForeignKey("kpis.id", ondelete="CASCADE"), index=True)
    value: Mapped[float] = mapped_column(Float)
    recorded_on: Mapped[date] = mapped_column(Date)
    note: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    kpi: Mapped[Kpi] = relationship(back_populates="readings")
