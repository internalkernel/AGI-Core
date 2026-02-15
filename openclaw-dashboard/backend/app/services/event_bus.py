"""Event bus for activity tracking — writes to PostgreSQL, Redis, and WebSocket."""

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Activity
from app.redis.client import get_redis
from app.websocket.manager import manager


class EventBus:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def emit(
        self,
        event_type: str,
        entity_type: str,
        entity_id: Optional[str] = None,
        details: Optional[dict] = None,
        actor: Optional[str] = None,
        status: Optional[str] = None,
    ):
        # 1. Persist to PostgreSQL
        activity = Activity(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            actor=actor,
            details=details,
            status=status,
        )
        self.session.add(activity)
        await self.session.commit()
        await self.session.refresh(activity)

        event_data = {
            "type": "activity",
            "data": {
                "id": str(activity.id),
                "event_type": event_type,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "actor": actor,
                "timestamp": activity.timestamp.isoformat(),
                "details": details,
                "status": status,
            },
        }

        # 2. Push to Redis recent list and publish
        redis = get_redis()
        if redis:
            serialized = json.dumps(event_data["data"])
            await redis.lpush("activity:recent", serialized)
            await redis.ltrim("activity:recent", 0, 99)
            await redis.publish(f"events:{event_type}", serialized)

        # 3. Broadcast via WebSocket
        await manager.broadcast(event_data, channel="activity")


async def get_event_bus(session=None):
    """Create an EventBus instance. For use with Depends() when session is injected."""
    from app.db.connection import get_session, async_session_factory
    if async_session_factory is None:
        yield None
        return
    async with async_session_factory() as sess:
        yield EventBus(sess)
