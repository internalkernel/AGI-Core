"""Webhook endpoint for agent activity events."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Depends
from pydantic import BaseModel

from app.config import settings
from app.services.event_bus import EventBus, get_event_bus

router = APIRouter(prefix="/api/webhook", tags=["webhook"])


class AgentActivityPayload(BaseModel):
    event_type: str
    agent_id: str
    agent_name: str = ""
    session_key: Optional[str] = None
    timestamp: Optional[str] = None
    details: Optional[dict] = None


@router.post("/activity")
async def receive_activity(
    payload: AgentActivityPayload,
    x_webhook_key: str = Header(...),
    event_bus: EventBus = Depends(get_event_bus),
):
    if not settings.webhook_api_key or x_webhook_key != settings.webhook_api_key:
        raise HTTPException(status_code=401, detail="Invalid webhook key")

    if event_bus:
        details = payload.details or {}
        if payload.session_key:
            details["session_key"] = payload.session_key
        if payload.timestamp:
            details["source_timestamp"] = payload.timestamp

        await event_bus.emit(
            event_type=payload.event_type,
            entity_type="agent",
            entity_id=payload.agent_id,
            actor=payload.agent_name or payload.agent_id,
            details=details if details else None,
        )

    return {"status": "accepted"}
