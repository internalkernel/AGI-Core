"""Chat proxy to OpenClaw agent gateways via WebSocket RPC protocol.

Each agent runs its own gateway on a dedicated port. The chat router
maps agent IDs to their gateway URLs and proxies WebSocket connections.
"""

import asyncio
import json
import time
import uuid

import httpx
import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from app.config import settings
from app.services.auth import authenticate_websocket
from app.services.gateway_rpc import (
    _handshake,
    AGENT_GATEWAYS,
    DEFAULT_AGENT,
    _agent_ws_url as _gateway_ws_url,
    _agent_token as _gateway_token,
)

router = APIRouter(tags=["chat"])

# Per-connection chat rate limit
_CHAT_MSGS_PER_MINUTE = 30


def _check_chat_rate(timestamps: list[float]) -> bool:
    """Return True if within rate limit, mutating timestamps in-place."""
    now = time.time()
    cutoff = now - 60
    timestamps[:] = [t for t in timestamps if t > cutoff]
    if len(timestamps) >= _CHAT_MSGS_PER_MINUTE:
        return False
    timestamps.append(now)
    return True


def _gateway_http_url(agent: str | None) -> str:
    ws_url = _gateway_ws_url(agent)
    return ws_url.replace("ws://", "http://").replace("wss://", "https://")


@router.get("/api/chat/status")
async def chat_status(agent: str | None = None):
    """Check if an agent's gateway is reachable."""
    url = _gateway_http_url(agent)
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{url}/health", timeout=1.0)
            return {
                "available": resp.status_code == 200,
                "gateway": url,
                "agent": agent or DEFAULT_AGENT,
            }
    except Exception:
        return {"available": False, "gateway": url, "agent": agent or DEFAULT_AGENT}


@router.get("/api/chat/agents")
async def chat_agents():
    """Return available agents and their gateway status."""
    results = []
    async with httpx.AsyncClient() as client:
        for agent_id, ws_url in AGENT_GATEWAYS.items():
            http_url = ws_url.replace("ws://", "http://").replace("wss://", "https://")
            try:
                resp = await client.get(f"{http_url}/health", timeout=1.0)
                available = resp.status_code == 200
            except Exception:
                available = False
            results.append({"id": agent_id, "available": available, "gateway": ws_url})
    return {"agents": results}


@router.post("/api/chat")
async def chat_proxy(request_data: dict):
    """Send a chat message via agent gateway and return the final response."""
    message = request_data.get("message", "").strip()
    if not message:
        return JSONResponse({"error": "Message is required"}, status_code=400)

    agent = request_data.get("agent")
    agent_id = agent or DEFAULT_AGENT
    session_key = request_data.get("sessionKey", "main")
    uri = _gateway_ws_url(agent_id)

    try:
        async with websockets.connect(uri, open_timeout=3, origin="http://localhost:8765") as gw:
            if not await _handshake(gw, _gateway_token(agent_id)):
                return JSONResponse({"error": "Gateway authentication failed"}, status_code=502)

            await gw.send(json.dumps({
                "type": "req",
                "id": "chat1",
                "method": "chat.send",
                "params": {
                    "sessionKey": session_key,
                    "message": message,
                    "deliver": False,
                    "idempotencyKey": str(uuid.uuid4()),
                },
            }))

            full_text = ""
            for _ in range(200):
                try:
                    raw = await asyncio.wait_for(gw.recv(), timeout=60)
                    msg = json.loads(raw)
                    ev = msg.get("event", "")
                    payload = msg.get("payload", {})

                    if ev == "health":
                        continue
                    if ev == "agent" and isinstance(payload, dict):
                        data = payload.get("data", {})
                        if payload.get("stream") == "assistant" and "delta" in data:
                            full_text += data["delta"]
                        if payload.get("stream") == "lifecycle" and data.get("phase") == "end":
                            break
                    if ev == "chat" and isinstance(payload, dict):
                        if payload.get("state") == "final":
                            content = payload.get("message", {}).get("content", [])
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    full_text = block["text"]
                            break
                except asyncio.TimeoutError:
                    break

            if full_text:
                return {"response": full_text, "agent": agent_id}
            else:
                return JSONResponse({"error": "No response from model"}, status_code=504)

    except (websockets.exceptions.ConnectionClosed, ConnectionRefusedError, OSError):
        return JSONResponse(
            {"error": f"Agent gateway ({agent_id}) is not running"},
            status_code=503,
        )
    except Exception as e:
        return JSONResponse({"error": "Chat request failed"}, status_code=500)


def _agent_label(agent_id: str) -> str:
    return agent_id.replace("-", " ").title()


def _build_context(history: list[dict], target_agent: str) -> str:
    """Build context from messages the target agent hasn't seen yet."""
    unseen = [m for m in history if target_agent not in m.get("seen_by", set())]
    if not unseen:
        return ""
    lines = []
    for m in unseen:
        name = _agent_label(m["agent"])
        if m["role"] == "user":
            lines.append(f"User (to {name}): {m['content']}")
        elif m["role"] == "assistant":
            lines.append(f"{name}: {m['content']}")
    return "[Other agents in this discussion]\n" + "\n".join(lines) + "\n\n"


@router.websocket("/ws/chat/collective")
async def websocket_collective_chat(websocket: WebSocket):
    """Collective chat — all agents share context via the backend.

    The backend opens persistent connections to every agent gateway and
    maintains a shared conversation history.  When the user addresses a
    specific agent, messages from *other* agents that haven't been seen
    yet are prepended as context so the addressed agent can follow the
    full discussion.
    """
    user_id = await authenticate_websocket(websocket)
    if not user_id:
        return

    MAX_HISTORY = 200
    MAX_MSG_SIZE = 32_768  # 32KB max message from client
    gateways: dict[str, websockets.WebSocketClientProtocol] = {}
    collective_history: list[dict] = []
    streaming_buf: dict[str, str] = {}          # per-agent streaming buffer

    # --- connect to all agent gateways ---
    for agent_id, ws_url in AGENT_GATEWAYS.items():
        try:
            gw = await websockets.connect(ws_url, open_timeout=3, origin="http://localhost:8765")
            if await _handshake(gw, _gateway_token(agent_id)):
                gateways[agent_id] = gw
        except Exception:
            pass

    available = list(gateways.keys())
    if not available:
        await websocket.send_json({
            "type": "connection_error",
            "error": "No agent gateways available",
        })
        try:
            await websocket.close()
        except Exception:
            pass
        return

    await websocket.send_json({
        "type": "system",
        "content": f"Collective chat ready — {len(available)} agents online: "
                   + ", ".join(_agent_label(a) for a in available),
    })

    # --- gateway → client relay (one per agent) ---
    async def gateway_listener(agent_id: str, gw):
        try:
            async for raw in gw:
                msg = json.loads(raw)
                ev = msg.get("event", "")
                payload = msg.get("payload", {})

                if ev == "health":
                    continue

                if ev == "agent" and isinstance(payload, dict):
                    data = payload.get("data", {})
                    if payload.get("stream") == "assistant" and "delta" in data:
                        streaming_buf.setdefault(agent_id, "")
                        streaming_buf[agent_id] += data["delta"]
                        await websocket.send_json({
                            "type": "delta",
                            "content": data["delta"],
                            "agent": agent_id,
                        })
                    elif payload.get("stream") == "lifecycle" and data.get("phase") == "end":
                        text = streaming_buf.pop(agent_id, "")
                        if text:
                            collective_history.append({
                                "role": "assistant",
                                "agent": agent_id,
                                "content": text,
                                "seen_by": {agent_id},
                            })
                        await websocket.send_json({
                            "type": "done",
                            "agent": agent_id,
                        })

                if ev == "chat" and isinstance(payload, dict) and payload.get("state") == "final":
                    content_blocks = payload.get("message", {}).get("content", [])
                    text = ""
                    for block in content_blocks:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text += block["text"]
                    if text:
                        streaming_buf.pop(agent_id, None)
                        collective_history.append({
                            "role": "assistant",
                            "agent": agent_id,
                            "content": text,
                            "seen_by": {agent_id},
                        })
                        await websocket.send_json({
                            "type": "message",
                            "content": text,
                            "role": "assistant",
                            "agent": agent_id,
                        })
        except websockets.exceptions.ConnectionClosed:
            pass

    # --- client → gateway router ---
    async def client_listener():
        rate_ts: list[float] = []
        try:
            while True:
                raw = await websocket.receive_text()
                if len(raw) > MAX_MSG_SIZE:
                    await websocket.send_json({"type": "error", "error": "Message too large"})
                    continue
                if not _check_chat_rate(rate_ts):
                    await websocket.send_json({"type": "error", "error": "Rate limit exceeded"})
                    continue
                data = json.loads(raw)
                content = data.get("content", data.get("message", ""))
                target = data.get("agent", DEFAULT_AGENT)

                if not content or target not in gateways:
                    continue

                # record user message (bounded history)
                collective_history.append({
                    "role": "user",
                    "agent": target,
                    "content": content,
                    "seen_by": {target},
                })
                if len(collective_history) > MAX_HISTORY:
                    del collective_history[:len(collective_history) - MAX_HISTORY]

                # build context from messages this agent hasn't seen
                context = _build_context(collective_history[:-1], target)
                full_message = f"{context}{content}" if context else content

                # mark all history as seen by target
                for entry in collective_history:
                    entry["seen_by"].add(target)

                streaming_buf.pop(target, None)

                await gateways[target].send(json.dumps({
                    "type": "req",
                    "id": str(uuid.uuid4())[:8],
                    "method": "chat.send",
                    "params": {
                        "sessionKey": "collective",
                        "message": full_message,
                        "deliver": False,
                        "idempotencyKey": str(uuid.uuid4()),
                    },
                }))
        except (WebSocketDisconnect, Exception):
            pass

    try:
        tasks = [client_listener()]
        for agent_id, gw in gateways.items():
            tasks.append(gateway_listener(agent_id, gw))
        await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        for gw in gateways.values():
            try:
                await gw.close()
            except Exception:
                pass
        try:
            await websocket.close()
        except Exception:
            pass


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket, agent: str | None = None):
    """WebSocket chat proxy — bridges the dashboard client to an agent gateway."""
    user_id = await authenticate_websocket(websocket)
    if not user_id:
        return
    agent_id = agent or DEFAULT_AGENT
    uri = _gateway_ws_url(agent_id)

    try:
        async with websockets.connect(uri, open_timeout=3, origin="http://localhost:8765") as gw:
            if not await _handshake(gw, _gateway_token(agent_id)):
                await websocket.send_json({
                    "type": "connection_error",
                    "error": f"Gateway authentication failed for {agent_id}",
                })
                return

            await websocket.send_json({
                "type": "system",
                "content": f"Connected to {agent_id}",
                "agent": agent_id,
            })

            async def gateway_to_client():
                try:
                    async for raw in gw:
                        msg = json.loads(raw)
                        ev = msg.get("event", "")
                        payload = msg.get("payload", {})

                        if ev == "health":
                            continue

                        if ev == "agent" and isinstance(payload, dict):
                            data = payload.get("data", {})
                            if payload.get("stream") == "assistant" and "delta" in data:
                                await websocket.send_json({
                                    "type": "delta",
                                    "content": data["delta"],
                                    "agent": agent_id,
                                    "runId": payload.get("runId"),
                                })
                            elif payload.get("stream") == "lifecycle" and data.get("phase") == "end":
                                await websocket.send_json({
                                    "type": "done",
                                    "agent": agent_id,
                                    "runId": payload.get("runId"),
                                })

                        if ev == "chat" and isinstance(payload, dict) and payload.get("state") == "final":
                            content_blocks = payload.get("message", {}).get("content", [])
                            text = ""
                            for block in content_blocks:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    text += block["text"]
                            if text:
                                await websocket.send_json({
                                    "type": "message",
                                    "content": text,
                                    "role": "assistant",
                                    "agent": agent_id,
                                })
                except websockets.exceptions.ConnectionClosed:
                    pass

            async def client_to_gateway():
                MAX_MSG_SIZE = 32_768  # 32KB
                rate_ts: list[float] = []
                try:
                    while True:
                        raw = await websocket.receive_text()
                        if len(raw) > MAX_MSG_SIZE:
                            await websocket.send_json({"type": "error", "error": "Message too large"})
                            continue
                        if not _check_chat_rate(rate_ts):
                            await websocket.send_json({"type": "error", "error": "Rate limit exceeded"})
                            continue
                        data = json.loads(raw)
                        message = data.get("content", data.get("message", ""))
                        session_key = data.get("sessionKey", "main")

                        if message:
                            await gw.send(json.dumps({
                                "type": "req",
                                "id": str(uuid.uuid4())[:8],
                                "method": "chat.send",
                                "params": {
                                    "sessionKey": session_key,
                                    "message": message,
                                    "deliver": False,
                                    "idempotencyKey": str(uuid.uuid4()),
                                },
                            }))
                except (WebSocketDisconnect, Exception):
                    pass

            await asyncio.gather(
                gateway_to_client(),
                client_to_gateway(),
                return_exceptions=True,
            )
    except (websockets.exceptions.ConnectionClosed, ConnectionRefusedError, OSError):
        try:
            await websocket.send_json({
                "type": "connection_error",
                "error": f"Agent gateway ({agent_id}) unavailable",
            })
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
