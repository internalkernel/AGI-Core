"""Global search endpoint — full-text search across activities, calendar, and discovery cache."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_session
from app.discovery.engine import get_cached_result
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
async def search(
    q: str = Query(..., min_length=1),
    type: str = Query(default="all"),
    limit: int = Query(default=20, le=50),
    _user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    results = {}
    search_term = q.strip()

    if type in ("all", "activity"):
        # Full-text search on activities — search in event_type, entity_type, entity_id, actor, and details
        stmt = text("""
            SELECT id::text, event_type, entity_type, entity_id, actor,
                   timestamp, details, status
            FROM activities
            WHERE event_type ILIKE :pattern
               OR entity_type ILIKE :pattern
               OR entity_id ILIKE :pattern
               OR actor ILIKE :pattern
               OR details::text ILIKE :pattern
            ORDER BY timestamp DESC
            LIMIT :lim
        """)
        res = await session.execute(stmt, {"pattern": f"%{search_term}%", "lim": limit})
        results["activities"] = [
            {
                "id": row[0], "event_type": row[1], "entity_type": row[2],
                "entity_id": row[3], "actor": row[4],
                "timestamp": row[5].isoformat() if row[5] else None,
                "details": row[6], "status": row[7],
            }
            for row in res.fetchall()
        ]

    if type in ("all", "calendar"):
        stmt = text("""
            SELECT id::text, title, description, start_time, end_time, all_day, source
            FROM calendar_events
            WHERE title ILIKE :pattern OR description ILIKE :pattern
            ORDER BY start_time DESC
            LIMIT :lim
        """)
        res = await session.execute(stmt, {"pattern": f"%{search_term}%", "lim": limit})
        results["calendar"] = [
            {
                "id": row[0], "title": row[1], "description": row[2],
                "start_time": row[3].isoformat() if row[3] else None,
                "end_time": row[4].isoformat() if row[4] else None,
                "all_day": row[5], "source": row[6],
            }
            for row in res.fetchall()
        ]

    if type in ("all", "agents", "skills", "jobs"):
        # Search in-memory discovery cache
        discovery = get_cached_result()
        if discovery:
            pattern = search_term.lower()
            if type in ("all", "agents"):
                results["agents"] = [
                    a for a in (discovery.get("agents") or [])
                    if pattern in str(a).lower()
                ][:limit]
            if type in ("all", "skills"):
                results["skills"] = [
                    s for s in (discovery.get("skills") or [])
                    if pattern in str(s).lower()
                ][:limit]

    return {"query": search_term, "results": results}
