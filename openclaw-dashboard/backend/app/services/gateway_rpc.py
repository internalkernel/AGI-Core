"""Shared Gateway RPC service — WebSocket challenge-response + RPC calls.

Extracted from chat.py for reuse by cron, config, node, session, and debug routers.
Each agent runs its own gateway on a dedicated port — the mapping lives here so
every router can resolve agent IDs to the correct gateway.
"""

import asyncio
import json
import logging
import uuid
from typing import Any, AsyncGenerator, Dict, Optional

import websockets

from app.config import settings

logger = logging.getLogger("gateway_rpc")

# Gateway WebSocket protocol constants
CLIENT_ID = "cli"
CLIENT_MODE = "cli"
ROLE = "operator"
SCOPES = ["operator.admin"]
PROTOCOL_VERSION = 3

# Timeouts
HANDSHAKE_TIMEOUT = 5
RPC_TIMEOUT = 30

# Agent → gateway WebSocket mapping
AGENT_GATEWAYS: dict[str, str] = {
    "content-specialist": "ws://127.0.0.1:8410",
    "devops": "ws://127.0.0.1:8420",
    "support-coordinator": "ws://127.0.0.1:8430",
    "wealth-strategist": "ws://127.0.0.1:8440",
}

DEFAULT_AGENT = "content-specialist"


def _load_agent_tokens() -> dict[str, str]:
    """Load per-agent tokens from OPENCLAW_DASH_AGENT_TOKENS env var (JSON)."""
    raw = settings.agent_tokens
    if raw:
        try:
            return json.loads(raw)
        except Exception:
            pass
    return {}


def _agent_ws_url(agent: str | None) -> str:
    """Resolve an agent ID to its gateway WebSocket URL."""
    if agent and agent in AGENT_GATEWAYS:
        return AGENT_GATEWAYS[agent]
    return AGENT_GATEWAYS.get(DEFAULT_AGENT, settings.gateway_ws_url)


def _agent_token(agent: str | None) -> str:
    """Resolve an agent ID to its gateway auth token."""
    agent_id = agent or DEFAULT_AGENT
    tokens = _load_agent_tokens()
    return tokens.get(agent_id, settings.gateway_token)


def _req_id() -> str:
    return str(uuid.uuid4())[:8]


async def _handshake(ws_conn, token: str | None = None) -> bool:
    """Perform the gateway challenge-response handshake. Returns True on success.

    Args:
        ws_conn: WebSocket connection to the gateway.
        token: Override token. Falls back to settings.gateway_token if not provided.
    """
    raw = await asyncio.wait_for(ws_conn.recv(), timeout=HANDSHAKE_TIMEOUT)
    msg = json.loads(raw)
    if msg.get("event") != "connect.challenge":
        return False

    auth_token = token or settings.gateway_token

    connect_msg = {
        "type": "req",
        "id": _req_id(),
        "method": "connect",
        "params": {
            "minProtocol": PROTOCOL_VERSION,
            "maxProtocol": PROTOCOL_VERSION,
            "client": {
                "id": CLIENT_ID,
                "version": "2.0.0",
                "platform": "linux",
                "mode": CLIENT_MODE,
                "instanceId": str(uuid.uuid4()),
            },
            "role": ROLE,
            "scopes": SCOPES,
            "auth": {"token": auth_token},
            "caps": [],
        },
    }
    await ws_conn.send(json.dumps(connect_msg))

    raw = await asyncio.wait_for(ws_conn.recv(), timeout=HANDSHAKE_TIMEOUT)
    msg = json.loads(raw)
    return msg.get("ok", False)


async def gateway_call(
    method: str,
    params: Optional[Dict[str, Any]] = None,
    timeout: float = RPC_TIMEOUT,
    agent: Optional[str] = None,
) -> Dict[str, Any]:
    """Open WebSocket, perform handshake, send RPC request, return response, close.

    Returns the full response dict. Raises on connection or timeout errors.
    When *agent* is provided the call is routed to that agent's gateway.
    """
    uri = _agent_ws_url(agent) if agent else settings.gateway_ws_url
    token = _agent_token(agent) if agent else None
    async with websockets.connect(uri, open_timeout=3, origin="http://localhost:8765") as gw:
        if not await _handshake(gw, token):
            raise ConnectionError("Gateway authentication failed")

        req_id = _req_id()
        await gw.send(json.dumps({
            "type": "req",
            "id": req_id,
            "method": method,
            "params": params or {},
        }))

        logger.info("RPC call: method=%s id=%s", method, req_id)

        # Wait for the response matching our request id
        for _ in range(100):
            raw = await asyncio.wait_for(gw.recv(), timeout=timeout)
            msg = json.loads(raw)

            # Skip health pings
            if msg.get("event") == "health":
                continue

            # Direct response to our request
            if msg.get("id") == req_id:
                logger.info("RPC response: method=%s ok=%s", method, msg.get("ok"))
                return msg

            # Some RPC methods return results via events instead
            if msg.get("type") == "res":
                logger.info("RPC response: method=%s ok=%s", method, msg.get("ok"))
                return msg

        raise TimeoutError(f"No response for RPC method {method}")


async def gateway_call_streaming(
    method: str,
    params: Optional[Dict[str, Any]] = None,
    timeout: float = RPC_TIMEOUT,
    agent: Optional[str] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Open WebSocket, perform handshake, send RPC request, yield events."""
    uri = _agent_ws_url(agent) if agent else settings.gateway_ws_url
    token = _agent_token(agent) if agent else None
    async with websockets.connect(uri, open_timeout=3, origin="http://localhost:8765") as gw:
        if not await _handshake(gw, token):
            raise ConnectionError("Gateway authentication failed")

        req_id = _req_id()
        await gw.send(json.dumps({
            "type": "req",
            "id": req_id,
            "method": method,
            "params": params or {},
        }))

        logger.info("RPC streaming call: method=%s id=%s", method, req_id)

        for _ in range(500):
            try:
                raw = await asyncio.wait_for(gw.recv(), timeout=timeout)
                msg = json.loads(raw)

                if msg.get("event") == "health":
                    continue

                yield msg

                # End on lifecycle end or final response
                ev = msg.get("event", "")
                payload = msg.get("payload", {})
                if isinstance(payload, dict):
                    data = payload.get("data", {})
                    if (
                        ev == "agent"
                        and payload.get("stream") == "lifecycle"
                        and data.get("phase") == "end"
                    ):
                        break
                    if ev == "chat" and payload.get("state") == "final":
                        break

                # Direct response means we're done
                if msg.get("id") == req_id and msg.get("type") == "res":
                    break

            except asyncio.TimeoutError:
                break


async def gateway_health_check(agent: Optional[str] = None) -> bool:
    """Quick check if gateway WebSocket is reachable and auth works."""
    try:
        uri = _agent_ws_url(agent) if agent else settings.gateway_ws_url
        token = _agent_token(agent) if agent else None
        async with websockets.connect(uri, open_timeout=2, origin="http://localhost:8765") as gw:
            return await _handshake(gw, token)
    except Exception:
        return False
