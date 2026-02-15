"""Calendar endpoints — CRUD for dashboard events + Google Calendar integration."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.db.connection import get_session
from app.models.database import CalendarEvent
from app.services.auth import get_current_user
from app.services.calendar import (
    get_merged_feed,
    get_google_calendar_enabled,
    set_google_calendar_enabled,
)

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


class CalendarEventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    all_day: bool = False


class CalendarEventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    all_day: Optional[bool] = None


@router.get("/events")
async def list_events(
    start: Optional[str] = None,
    end: Optional[str] = None,
    include_google: bool = Query(default=True),
    _user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    now = datetime.now(timezone.utc)
    start_dt = datetime.fromisoformat(start) if start else now.replace(day=1, hour=0, minute=0, second=0)
    end_dt = datetime.fromisoformat(end) if end else now.replace(month=now.month % 12 + 1 if now.month < 12 else 1, day=28)
    return await get_merged_feed(start_dt, end_dt, include_google, session)


@router.post("/events")
async def create_event(
    body: CalendarEventCreate,
    _user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    event = CalendarEvent(
        title=body.title,
        description=body.description,
        start_time=body.start_time,
        end_time=body.end_time,
        all_day=body.all_day,
        source="dashboard",
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return {
        "id": str(event.id),
        "title": event.title,
        "start_time": event.start_time.isoformat(),
        "end_time": event.end_time.isoformat() if event.end_time else None,
    }


@router.put("/events/{event_id}")
async def update_event(
    event_id: str,
    body: CalendarEventUpdate,
    _user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(CalendarEvent).where(CalendarEvent.id == uuid.UUID(event_id))
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.source != "dashboard":
        raise HTTPException(status_code=400, detail="Cannot edit Google Calendar events")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(event, field, value)
    await session.commit()
    return {"message": "Updated"}


@router.delete("/events/{event_id}")
async def delete_event(
    event_id: str,
    _user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(CalendarEvent).where(CalendarEvent.id == uuid.UUID(event_id))
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.source != "dashboard":
        raise HTTPException(status_code=400, detail="Cannot delete Google Calendar events")
    await session.delete(event)
    await session.commit()
    return {"message": "Deleted"}


@router.get("/settings")
async def get_settings(
    _user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    enabled = await get_google_calendar_enabled(session)
    return {"google_calendar_enabled": enabled}


@router.put("/settings")
async def update_settings(
    body: dict,
    _user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if "google_calendar_enabled" in body:
        await set_google_calendar_enabled(body["google_calendar_enabled"], session)
    return {"message": "Settings updated"}
