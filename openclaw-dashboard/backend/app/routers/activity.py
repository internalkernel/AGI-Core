"""Activity feed endpoints — paginated history and stats."""

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.db.connection import get_session
from app.models.database import Activity
from app.redis.client import get_redis
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/activity", tags=["activity"])


@router.get("")
async def list_activities(
    entity_type: Optional[str] = None,
    event_type: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    _user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Activity).order_by(Activity.timestamp.desc())
    if entity_type:
        stmt = stmt.where(Activity.entity_type == entity_type)
    if event_type:
        stmt = stmt.where(Activity.event_type == event_type)
    if since:
        stmt = stmt.where(Activity.timestamp >= datetime.fromisoformat(since))
    if until:
        stmt = stmt.where(Activity.timestamp <= datetime.fromisoformat(until))
    stmt = stmt.offset(offset).limit(limit)
    result = await session.execute(stmt)
    activities = result.scalars().all()
    return [
        {
            "id": str(a.id),
            "event_type": a.event_type,
            "entity_type": a.entity_type,
            "entity_id": a.entity_id,
            "actor": a.actor,
            "timestamp": a.timestamp.isoformat(),
            "details": a.details,
            "status": a.status,
        }
        for a in activities
    ]


@router.get("/recent")
async def recent_activities(_user=Depends(get_current_user)):
    """Get recent activities from Redis cache (fast)."""
    redis = get_redis()
    if redis:
        items = await redis.lrange("activity:recent", 0, 49)
        return [json.loads(item) for item in items]
    return []


@router.get("/stats")
async def activity_stats(
    _user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Counts of activities by entity_type for dashboard widgets."""
    stmt = (
        select(Activity.entity_type, func.count(Activity.id))
        .group_by(Activity.entity_type)
    )
    result = await session.execute(stmt)
    return {row[0]: row[1] for row in result.all()}
