"""Calendar service — dashboard events + optional Google Calendar via gwcli."""

import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.database import CalendarEvent, DashboardSetting


async def get_dashboard_events(
    start: datetime, end: datetime, session: AsyncSession
) -> list[CalendarEvent]:
    stmt = (
        select(CalendarEvent)
        .where(CalendarEvent.source == "dashboard")
        .where(CalendarEvent.start_time >= start)
        .where(CalendarEvent.start_time <= end)
        .order_by(CalendarEvent.start_time)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_google_events(days: int = 30) -> list[dict]:
    """Shell out to gwcli for Google Calendar events."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "gwcli", "calendar", "events", "--days", str(days), "--format", "json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
        if proc.returncode == 0 and stdout:
            return json.loads(stdout.decode())
        return []
    except Exception:
        return []


async def create_google_event(
    title: str,
    start_time: str,
    end_time: Optional[str] = None,
    description: Optional[str] = None,
    all_day: bool = False,
) -> Optional[str]:
    """Create an event on Google Calendar via gwcli. Returns Google event ID or None."""
    try:
        args = ["gwcli", "calendar", "create", "--title", title, "--start", start_time]
        if end_time:
            args.extend(["--end", end_time])
        if description:
            args.extend(["--description", description])
        if all_day:
            args.append("--all-day")
        args.extend(["--format", "json"])

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
        if proc.returncode == 0 and stdout:
            data = json.loads(stdout.decode())
            return data.get("id") or data.get("eventId")
        return None
    except Exception:
        return None


async def get_google_calendar_enabled(session: AsyncSession) -> bool:
    result = await session.execute(
        select(DashboardSetting).where(DashboardSetting.key == "google_calendar_enabled")
    )
    setting = result.scalar_one_or_none()
    if setting and setting.value:
        return setting.value.get("enabled", False)
    return False


async def set_google_calendar_enabled(enabled: bool, session: AsyncSession):
    result = await session.execute(
        select(DashboardSetting).where(DashboardSetting.key == "google_calendar_enabled")
    )
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = {"enabled": enabled}
        setting.updated_at = datetime.now(timezone.utc)
    else:
        setting = DashboardSetting(
            key="google_calendar_enabled",
            value={"enabled": enabled},
        )
        session.add(setting)
    await session.commit()


async def get_merged_feed(
    start: datetime,
    end: datetime,
    include_google: bool,
    session: AsyncSession,
) -> list[dict]:
    dashboard_events = await get_dashboard_events(start, end, session)
    events = [
        {
            "id": str(e.id),
            "title": e.title,
            "description": e.description,
            "start_time": e.start_time.isoformat(),
            "end_time": e.end_time.isoformat() if e.end_time else None,
            "all_day": e.all_day,
            "source": "dashboard",
            "agent": e.agent,
        }
        for e in dashboard_events
    ]

    if include_google and await get_google_calendar_enabled(session):
        days = max(1, (end - start).days)
        google_events = await get_google_events(days)
        for ge in google_events:
            events.append({
                "id": ge.get("id", ""),
                "title": ge.get("summary", ""),
                "description": ge.get("description", ""),
                "start_time": ge.get("start", ""),
                "end_time": ge.get("end", ""),
                "all_day": ge.get("all_day", False),
                "source": "google",
            })

    events.sort(key=lambda e: e.get("start_time", ""))
    return events
