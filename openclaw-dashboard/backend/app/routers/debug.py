"""Debug and diagnostics endpoints using gateway RPC."""

import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.config import settings
from app.services.gateway_rpc import (
    gateway_call,
    gateway_health_check,
    _agent_ws_url,
    AGENT_GATEWAYS,
)

router = APIRouter(tags=["debug"])


@router.get("/api/debug/health")
async def debug_health(agent: Optional[str] = Query(None)):
    """Detailed health check via gateway RPC."""
    try:
        result = await gateway_call("health", agent=agent)
        if result.get("ok"):
            return result.get("result", {})
    except Exception:
        pass
    return {"status": "gateway_unreachable", "timestamp": time.time()}


@router.get("/api/debug/status")
async def debug_status(agent: Optional[str] = Query(None)):
    """Full system status via gateway RPC."""
    try:
        result = await gateway_call("status", agent=agent)
        if result.get("ok"):
            return result.get("result", {})
    except Exception:
        pass
    return {"status": "unavailable"}


@router.get("/api/debug/presence")
async def debug_presence(agent: Optional[str] = Query(None)):
    """System presence via gateway RPC."""
    try:
        result = await gateway_call("system-presence", agent=agent)
        if result.get("ok"):
            return result.get("result", {})
    except Exception:
        pass
    return {"presence": "unknown"}


@router.get("/api/debug/gateway")
async def debug_gateway(agent: Optional[str] = Query(None)):
    """Test gateway connection — connect and disconnect."""
    start = time.time()
    gateway_url = _agent_ws_url(agent) if agent else settings.gateway_ws_url
    try:
        ok = await gateway_health_check(agent=agent)
        latency_ms = round((time.time() - start) * 1000)
        return {
            "connected": ok,
            "latency_ms": latency_ms,
            "gateway_url": gateway_url,
            "agent": agent,
            "protocol_version": 3,
        }
    except Exception as e:
        latency_ms = round((time.time() - start) * 1000)
        return {
            "connected": False,
            "latency_ms": latency_ms,
            "gateway_url": gateway_url,
            "agent": agent,
            "error": str(e),
        }


@router.get("/api/debug/sessions")
async def debug_sessions(agent: Optional[str] = Query(None)):
    """Sessions with usage via gateway RPC."""
    sessions = []
    try:
        result = await gateway_call("sessions.list", agent=agent)
        if result.get("ok"):
            sessions = result.get("result", {}).get("sessions", [])
    except Exception:
        pass

    # Try to get usage for each session
    enriched = []
    for s in sessions[:20]:
        session_data = dict(s) if isinstance(s, dict) else {"id": str(s)}
        try:
            sid = session_data.get("id", "")
            if sid:
                usage = await gateway_call("sessions.usage", {"sessionId": sid}, agent=agent)
                if usage.get("ok"):
                    session_data["usage"] = usage.get("result", {})
        except Exception:
            pass
        enriched.append(session_data)

    return {"sessions": enriched}


@router.get("/api/debug/logs")
async def debug_logs(agent: Optional[str] = Query(None)):
    """Recent logs via gateway RPC."""
    try:
        result = await gateway_call("logs.tail", {"lines": 100}, agent=agent)
        if result.get("ok"):
            return result.get("result", {})
    except Exception:
        pass

    # Fallback: read from log files directly
    logs_dir = settings.openclaw_dir / "logs"
    lines = []
    if logs_dir.exists():
        for log_file in sorted(logs_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)[:1]:
            try:
                content = log_file.read_text()
                lines = content.strip().split("\n")[-100:]
            except Exception:
                pass
    return {"lines": lines, "source": "file"}


@router.get("/api/debug/filesystem")
async def debug_filesystem(agent: Optional[str] = Query(None)):
    """Check critical file system paths.

    When an agent is specified the workspace path is scoped to that agent.
    """
    base = settings.openclaw_dir
    checks = {}

    # Common paths
    paths: dict[str, Path] = {
        "cron_dir": base / "cron",
        "logs_dir": base / "logs",
        "config_file": base / "openclaw.json",
        "devices_dir": base / "devices",
    }

    # Agent-scoped workspace & sessions
    if agent and agent in AGENT_GATEWAYS:
        paths["workspace"] = base / f"workspace-{agent}"
        paths["projects"] = base / f"workspace-{agent}" / "projects"
        paths["sessions_dir"] = base / "agents" / agent / "sessions"
    else:
        paths["workspace"] = base / "workspace"
        paths["sessions_dir"] = base / "agents" / "main" / "sessions"

    for name, path in paths.items():
        checks[name] = {
            "path": str(path),
            "exists": path.exists(),
            "readable": path.exists() and (path.is_file() or path.is_dir()),
        }
    return {"checks": checks}
