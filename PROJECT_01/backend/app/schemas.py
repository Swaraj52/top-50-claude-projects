from __future__ import annotations

import re
from datetime import date, datetime
from typing import Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from .timeutil import is_valid_timezone

Priority = Literal["low", "medium", "high"]
TaskStatus = Literal["todo", "done"]
HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def _check_tz(value: str) -> str:
    if not is_valid_timezone(value):
        raise ValueError("unknown timezone")
    return value


# --- auth -------------------------------------------------------------------


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=80)
    timezone: str = "UTC"

    _tz = field_validator("timezone")(_check_tz)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name is required")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(ORM):
    id: int
    email: str
    name: str
    timezone: str


class UserPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    timezone: str | None = None

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str | None) -> str | None:
        return None if v is None else _check_tz(v)


# --- tasks ------------------------------------------------------------------


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    notes: str = Field(default="", max_length=5000)
    priority: Priority = "medium"
    due_date: date | None = None

    @field_validator("title")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("title is required")
        return v


class TaskPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=5000)
    priority: Priority | None = None
    status: TaskStatus | None = None
    due_date: date | None = None


class TaskOut(ORM):
    id: int
    title: str
    notes: str
    priority: Priority
    status: TaskStatus
    due_date: date | None
    completed_at: datetime | None
    created_at: datetime


# --- reminders --------------------------------------------------------------


class ReminderIn(BaseModel):
    text: str = Field(min_length=1, max_length=200)
    remind_at: AwareDatetime
    task_id: int | None = None


class ReminderPatch(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=200)
    remind_at: AwareDatetime | None = None


class SnoozeIn(BaseModel):
    minutes: int = Field(ge=1, le=7 * 24 * 60)


class ReminderOut(ORM):
    id: int
    text: str
    remind_at: datetime
    status: Literal["pending", "dismissed"]
    task_id: int | None


# --- events / calendars -----------------------------------------------------


class EventIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    start_at: AwareDatetime
    end_at: AwareDatetime
    all_day: bool = False
    location: str = Field(default="", max_length=300)
    description: str = Field(default="", max_length=5000)

    @model_validator(mode="after")
    def _order(self):
        if self.end_at < self.start_at:
            raise ValueError("end_at must not be before start_at")
        return self


class EventPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    start_at: AwareDatetime | None = None
    end_at: AwareDatetime | None = None
    all_day: bool | None = None
    location: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None, max_length=5000)


class EventOut(BaseModel):
    id: int
    title: str
    location: str
    description: str
    start_at: datetime
    end_at: datetime
    all_day: bool
    source_id: int | None
    source_name: str | None
    color: str
    read_only: bool


class CalendarUrlIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    url: str = Field(min_length=8, max_length=2000)
    color: str = "#5b6cf0"

    @field_validator("url")
    @classmethod
    def _url(cls, v: str) -> str:
        v = v.strip()
        if v.startswith("webcal://"):
            v = "https://" + v[len("webcal://"):]
        if not re.match(r"^https?://[^\s/]+", v):
            raise ValueError("must be an http(s) or webcal URL")
        return v

    @field_validator("color")
    @classmethod
    def _color(cls, v: str) -> str:
        if not HEX_COLOR.match(v):
            raise ValueError("color must look like #RRGGBB")
        return v


class CalendarOut(ORM):
    id: int
    name: str
    kind: Literal["url", "file"]
    color: str
    last_synced_at: datetime | None
    last_error: str | None
    event_count: int


# --- email ------------------------------------------------------------------


class EmailAccountIn(BaseModel):
    host: str = Field(min_length=3, max_length=255, pattern=r"^[A-Za-z0-9.-]+$")
    port: int = Field(default=993, ge=1, le=65535)
    username: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=500)
    mailbox: str = Field(default="INBOX", min_length=1, max_length=100)


class EmailAccountOut(ORM):
    host: str
    port: int
    username: str
    mailbox: str
    last_synced_at: datetime | None
    last_error: str | None


class EmailOut(ORM):
    id: int
    from_name: str
    from_addr: str
    subject: str
    received_at: datetime
    is_unread: bool
    is_flagged: bool
    task_id: int | None


class EmailSyncOut(BaseModel):
    fetched: int
    attention: int


# --- priorities -------------------------------------------------------------


class PriorityItemIn(BaseModel):
    text: str = Field(min_length=1, max_length=200)
    task_id: int | None = None
    done: bool = False


class PrioritiesPut(BaseModel):
    day: date
    items: list[PriorityItemIn] = Field(max_length=3)


class PriorityPatch(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=200)
    done: bool | None = None


class PriorityOut(ORM):
    id: int
    day: date
    position: int
    text: str
    task_id: int | None
    done: bool


# --- briefing ---------------------------------------------------------------


class FocusItem(BaseModel):
    title: str = Field(max_length=200)
    reason: str = Field(max_length=300)
    task_id: int | None = None


class BriefingContent(BaseModel):
    headline: str = Field(max_length=200)
    summary: str = Field(max_length=1200)
    schedule_notes: list[str] = Field(default_factory=list, max_length=6)
    focus: list[FocusItem] = Field(default_factory=list, max_length=3)
    heads_up: list[str] = Field(default_factory=list, max_length=5)


class BriefingOut(ORM):
    id: int
    day: date
    source: Literal["ai", "rule"]
    model: str | None
    note: str | None
    content: BriefingContent
    created_at: datetime


# --- dashboard / meta -------------------------------------------------------


class DashboardCounts(BaseModel):
    overdue: int
    due_today: int
    done_today: int
    upcoming: int
    events_today: int
    unread_emails: int
    attention_emails: int


class DashboardOut(BaseModel):
    date: date
    timezone: str
    user_name: str
    events: list[EventOut]
    tasks: list[TaskOut]
    reminders: list[ReminderOut]
    priorities: list[PriorityOut]
    emails: list[EmailOut]
    email_connected: bool
    calendars_connected: int
    counts: DashboardCounts
    briefing: BriefingOut | None


class MetaOut(BaseModel):
    version: str
    ai_enabled: bool
    ai_model: str | None
