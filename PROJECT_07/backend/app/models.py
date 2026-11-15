from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, UTCDateTime, utcnow

CATEGORIES = ("reply", "waiting", "fyi", "newsletter", "receipt")
CATEGORY_SOURCES = ("rules", "you", "claude")
THREAD_STATUSES = ("open", "waiting", "closed")
DIRECTIONS = ("in", "out")
DRAFT_STATUSES = ("draft", "sent")
DRAFT_SOURCES = ("local", "claude")
FOLLOWUP_STATUSES = ("open", "done")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(255))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    signature: Mapped[str] = mapped_column(String(240), default="")
    vips: Mapped[str] = mapped_column(Text, default="")
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


class Mailbox(Base):
    __tablename__ = "mailboxes"
    __table_args__ = (UniqueConstraint("user_id", "address", name="uq_mailboxes_user_address"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(40))
    address: Mapped[str] = mapped_column(String(254))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    threads: Mapped[list["Thread"]] = relationship(back_populates="mailbox", cascade="all, delete-orphan")


class Thread(Base):
    __tablename__ = "threads"
    __table_args__ = (
        CheckConstraint(f"category IN {CATEGORIES}", name="ck_threads_category"),
        CheckConstraint(f"status IN {THREAD_STATUSES}", name="ck_threads_status"),
        Index("ix_threads_user_activity", "user_id", "last_activity_at"),
        Index("ix_threads_user_category", "user_id", "category"),
        Index("ix_threads_mailbox", "mailbox_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    mailbox_id: Mapped[int] = mapped_column(ForeignKey("mailboxes.id", ondelete="CASCADE"))
    subject: Mapped[str] = mapped_column(String(200))
    subject_key: Mapped[str] = mapped_column(String(200))
    participants: Mapped[str] = mapped_column(String(400), default="")
    category: Mapped[str] = mapped_column(String(12), default="fyi")
    category_source: Mapped[str] = mapped_column(String(10), default="rules")
    status: Mapped[str] = mapped_column(String(10), default="open")
    unread: Mapped[bool] = mapped_column(Boolean, default=True)
    starred: Mapped[bool] = mapped_column(Boolean, default=False)
    summary: Mapped[str] = mapped_column(Text, default="")
    summary_source: Mapped[str] = mapped_column(String(10), default="local")
    summary_note: Mapped[str] = mapped_column(String(300), default="")
    last_activity_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    mailbox: Mapped[Mailbox] = relationship(back_populates="threads")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="thread", cascade="all, delete-orphan", passive_deletes=True, order_by="Message.received_at"
    )
    drafts: Mapped[list["Draft"]] = relationship(
        back_populates="thread", cascade="all, delete-orphan", passive_deletes=True, order_by="Draft.id"
    )
    followups: Mapped[list["FollowUp"]] = relationship(
        back_populates="thread", cascade="all, delete-orphan", passive_deletes=True, order_by="FollowUp.id"
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(f"direction IN {DIRECTIONS}", name="ck_messages_direction"),
        Index("ix_messages_thread", "thread_id"),
        UniqueConstraint("user_id", "external_id", name="uq_messages_user_external"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    thread_id: Mapped[int] = mapped_column(ForeignKey("threads.id", ondelete="CASCADE"))
    direction: Mapped[str] = mapped_column(String(4), default="in")
    sender: Mapped[str] = mapped_column(String(254))
    recipients: Mapped[str] = mapped_column(String(400), default="")
    body: Mapped[str] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(UTCDateTime)
    external_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    thread: Mapped[Thread] = relationship(back_populates="messages")


class Draft(Base):
    __tablename__ = "drafts"
    __table_args__ = (
        CheckConstraint(f"status IN {DRAFT_STATUSES}", name="ck_drafts_status"),
        CheckConstraint(f"source IN {DRAFT_SOURCES}", name="ck_drafts_source"),
        Index("ix_drafts_thread", "thread_id"),
        Index("ix_drafts_user_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    thread_id: Mapped[int] = mapped_column(ForeignKey("threads.id", ondelete="CASCADE"))
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    tone: Mapped[str] = mapped_column(String(10), default="warm")
    source: Mapped[str] = mapped_column(String(10), default="local")
    status: Mapped[str] = mapped_column(String(10), default="draft")
    note: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    thread: Mapped[Thread] = relationship(back_populates="drafts")


class FollowUp(Base):
    __tablename__ = "followups"
    __table_args__ = (
        CheckConstraint(f"status IN {FOLLOWUP_STATUSES}", name="ck_followups_status"),
        Index("ix_followups_user_status_due", "user_id", "status", "due_date"),
        Index("ix_followups_thread", "thread_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    thread_id: Mapped[int] = mapped_column(ForeignKey("threads.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(240))
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="open")
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    thread: Mapped[Thread] = relationship(back_populates="followups")
