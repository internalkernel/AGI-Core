"""SQLModel database models for persistent storage."""

import uuid
from datetime import datetime, timezone
from typing import Optional, Any

from sqlmodel import SQLModel, Field
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP


def utcnow():
    return datetime.now(timezone.utc)


def new_uuid():
    return uuid.uuid4()


# Use timezone-aware TIMESTAMP for asyncpg compatibility
TZTimestamp = TIMESTAMP(timezone=True)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=new_uuid, primary_key=True)
    username: str = Field(index=True, unique=True)
    hashed_password: str
    is_admin: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(TZTimestamp, default=utcnow))
    last_login: Optional[datetime] = Field(default=None, sa_column=Column(TZTimestamp, nullable=True))


class Activity(SQLModel, table=True):
    __tablename__ = "activities"

    id: uuid.UUID = Field(default_factory=new_uuid, primary_key=True)
    event_type: str = Field(index=True)  # e.g. job.created, session.started
    entity_type: str = Field(index=True)  # e.g. job, session, config
    entity_id: Optional[str] = None
    actor: Optional[str] = None
    timestamp: datetime = Field(default_factory=utcnow, sa_column=Column(TZTimestamp, default=utcnow, index=True))
    details: Optional[dict] = Field(default=None, sa_column=Column(JSONB))
    status: Optional[str] = None


class CalendarEvent(SQLModel, table=True):
    __tablename__ = "calendar_events"

    id: uuid.UUID = Field(default_factory=new_uuid, primary_key=True)
    title: str
    description: Optional[str] = None
    start_time: datetime = Field(sa_column=Column(TZTimestamp, nullable=False))
    end_time: Optional[datetime] = Field(default=None, sa_column=Column(TZTimestamp, nullable=True))
    all_day: bool = Field(default=False)
    source: str = Field(default="dashboard")  # "dashboard" or "google"
    agent: Optional[str] = Field(default=None)  # agent id that owns this event
    google_event_id: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(TZTimestamp, default=utcnow))


class DashboardSetting(SQLModel, table=True):
    __tablename__ = "dashboard_settings"

    key: str = Field(primary_key=True)
    value: Optional[dict] = Field(default=None, sa_column=Column(JSONB))
    updated_at: datetime = Field(default_factory=utcnow, sa_column=Column(TZTimestamp, default=utcnow))
