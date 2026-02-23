"""Channels API — CRUD for communication channel configuration."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.services.auth import require_admin
from app.models.database import User

router = APIRouter(tags=["channels"])

CHANNELS_FILE = settings.openclaw_dir / "channels.json"

DEFAULT_CHANNELS: List[Dict[str, Any]] = [
    {
        "id": "slack",
        "name": "Slack",
        "icon": "slack",
        "enabled": False,
        "agents": [],
        "config": {"workspace": "", "bot_name": "OpenClaw Bot"},
        "always_show": True,
    },
    {
        "id": "discord",
        "name": "Discord",
        "icon": "discord",
        "enabled": False,
        "agents": [],
        "config": {"server": "", "bot_name": "OpenClaw Bot"},
        "always_show": True,
    },
]


class ChannelUpdate(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    enabled: Optional[bool] = None
    agents: Optional[List[str]] = None
    config: Optional[Dict[str, Any]] = None
    always_show: Optional[bool] = None


class ChannelCreate(BaseModel):
    id: str
    name: str
    icon: str = "message-square"
    enabled: bool = False
    agents: List[str] = []
    config: Dict[str, Any] = {}
    always_show: bool = False


def _read_channels() -> List[Dict[str, Any]]:
    if not CHANNELS_FILE.exists():
        CHANNELS_FILE.parent.mkdir(parents=True, exist_ok=True)
        CHANNELS_FILE.write_text(json.dumps(DEFAULT_CHANNELS, indent=2))
        return list(DEFAULT_CHANNELS)
    try:
        data = json.loads(CHANNELS_FILE.read_text())
        if isinstance(data, list):
            return data
        return list(DEFAULT_CHANNELS)
    except Exception:
        return list(DEFAULT_CHANNELS)


def _write_channels(channels: List[Dict[str, Any]]):
    CHANNELS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHANNELS_FILE.write_text(json.dumps(channels, indent=2))


@router.get("/api/channels")
async def list_channels():
    channels = _read_channels()
    return {"channels": channels, "total": len(channels)}


@router.get("/api/channels/{channel_id}")
async def get_channel(channel_id: str):
    channels = _read_channels()
    for ch in channels:
        if ch["id"] == channel_id:
            return ch
    raise HTTPException(status_code=404, detail="Channel not found")


@router.put("/api/channels/{channel_id}")
async def update_channel(channel_id: str, update: ChannelUpdate, _admin: User = Depends(require_admin)):
    channels = _read_channels()
    for ch in channels:
        if ch["id"] == channel_id:
            update_data = update.model_dump(exclude_none=True)
            ch.update(update_data)
            _write_channels(channels)
            return {"status": "updated", "channel": ch}
    raise HTTPException(status_code=404, detail="Channel not found")


@router.post("/api/channels")
async def create_channel(channel: ChannelCreate, _admin: User = Depends(require_admin)):
    channels = _read_channels()
    for ch in channels:
        if ch["id"] == channel.id:
            raise HTTPException(status_code=409, detail="Channel already exists")
    new_channel = channel.model_dump()
    channels.append(new_channel)
    _write_channels(channels)
    return {"status": "created", "channel": new_channel}


@router.delete("/api/channels/{channel_id}")
async def delete_channel(channel_id: str, _admin: User = Depends(require_admin)):
    channels = _read_channels()
    original_len = len(channels)
    channels = [ch for ch in channels if ch["id"] != channel_id]
    if len(channels) == original_len:
        raise HTTPException(status_code=404, detail="Channel not found")
    _write_channels(channels)
    return {"status": "deleted"}
