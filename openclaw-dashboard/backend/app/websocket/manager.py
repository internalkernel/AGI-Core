"""Multi-channel WebSocket connection manager."""

import asyncio
import time
from typing import Dict, Set
from fastapi import WebSocket


# Limits
MAX_CONNECTIONS_PER_CHANNEL = 50
MAX_MESSAGES_PER_MINUTE = 60


class ConnectionManager:
    def __init__(self):
        self.channels: Dict[str, Set[WebSocket]] = {}
        self._msg_counts: Dict[WebSocket, list] = {}  # ws -> [timestamps]

    async def connect(self, websocket: WebSocket, channel: str = "default", accepted: bool = False):
        if not accepted:
            await websocket.accept()
        if channel not in self.channels:
            self.channels[channel] = set()
        if len(self.channels[channel]) >= MAX_CONNECTIONS_PER_CHANNEL:
            await websocket.close(code=1013, reason="Too many connections")
            return False
        self.channels[channel].add(websocket)
        self._msg_counts[websocket] = []
        return True

    def disconnect(self, websocket: WebSocket, channel: str = "default"):
        if channel in self.channels:
            self.channels[channel].discard(websocket)
        self._msg_counts.pop(websocket, None)

    def check_rate(self, websocket: WebSocket) -> bool:
        """Return True if the message is within rate limits."""
        now = time.time()
        timestamps = self._msg_counts.get(websocket, [])
        cutoff = now - 60
        timestamps = [t for t in timestamps if t > cutoff]
        if len(timestamps) >= MAX_MESSAGES_PER_MINUTE:
            self._msg_counts[websocket] = timestamps
            return False
        timestamps.append(now)
        self._msg_counts[websocket] = timestamps
        return True

    async def broadcast(self, message: dict, channel: str = "default"):
        if channel not in self.channels:
            return
        dead = []
        for ws in self.channels[channel]:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.channels[channel].discard(ws)
            self._msg_counts.pop(ws, None)


manager = ConnectionManager()
