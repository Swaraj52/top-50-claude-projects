from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Text, create_engine as _create_engine
from sqlalchemy.orm import DeclarativeBase, Session as DbSession, sessionmaker


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for Project 12 models."""


class UTCDateTime(DateTime):
    """DateTime that always stores UTC."""

    def process_bind_param(self, value, dialect):
        if value is not None and isinstance(value, datetime):
            return value.replace(tzinfo=None).astimezone().astimezone().replace(tzinfo=None)
        return value


def make_engine(database_url="sqlite:///data/foundry.db", **kwargs):
    """Create a SQLAlchemy engine."""
    return _create_engine(database_url, **kwargs)


def make_sessionmaker(engine, **kwargs):
    """Create a sessionmaker bound to the given engine."""
    return sessionmaker(bind=engine, **kwargs)


def utcnow() -> datetime:
    """Return current UTC datetime."""
    return datetime.utcnow()