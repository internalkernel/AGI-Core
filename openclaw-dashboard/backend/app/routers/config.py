"""Configuration management endpoints using gateway RPC."""

import json
from pathlib import Path
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.config import settings
from app.services.gateway_rpc import gateway_call
from app.services.event_bus import EventBus, get_event_bus
from app.services.auth import require_admin
from app.models.database import User

router = APIRouter(tags=["config"])

# Keys that must never be exposed in API responses
_SECRET_PATHS = {"gateway.auth.token", "auth.profiles", "auth.token", "tokens"}
_SECRET_KEY_NAMES = {"token", "secret", "password", "api_key", "apikey", "auth_token"}


def _redact_secrets(data: dict, prefix: str = "") -> dict:
    """Recursively redact secret values from config."""
    result = {}
    for k, v in data.items():
        path = f"{prefix}.{k}" if prefix else k
        is_secret = (
            any(path.startswith(s) for s in _SECRET_PATHS)
            or k.lower() in _SECRET_KEY_NAMES
        )
        if is_secret:
            if isinstance(v, str):
                result[k] = "***REDACTED***"
            elif isinstance(v, dict):
                result[k] = {kk: "***REDACTED***" for kk in v}
            else:
                result[k] = "***REDACTED***"
        elif isinstance(v, dict):
            result[k] = _redact_secrets(v, path)
        elif isinstance(v, list):
            result[k] = _redact_list(v, path)
        else:
            result[k] = v
    return result


def _redact_list(items: list, prefix: str) -> list:
    """Recursively redact secrets inside list values."""
    out = []
    for item in items:
        if isinstance(item, dict):
            out.append(_redact_secrets(item, prefix))
        elif isinstance(item, list):
            out.append(_redact_list(item, prefix))
        else:
            out.append(item)
    return out


@router.get("/api/config")
async def get_config(_admin: User = Depends(require_admin)):
    """Get current config — tries RPC first, falls back to file."""
    try:
        result = await gateway_call("config.get")
        if result.get("ok") and result.get("result"):
            return _redact_secrets(result["result"])
    except Exception:
        pass
    # Fallback: read from file
    config_file = settings.openclaw_dir / "openclaw.json"
    try:
        if config_file.exists():
            data = json.loads(config_file.read_text())
            return _redact_secrets(data)
    except Exception:
        pass
    return {}


@router.get("/api/config/schema")
async def get_config_schema(_admin: User = Depends(require_admin)):
    """Get config schema via RPC."""
    try:
        result = await gateway_call("config.schema")
        if result.get("ok"):
            return result.get("result", {})
    except Exception:
        pass
    return {"error": "Schema not available"}


@router.put("/api/config")
async def update_config(data: dict, _admin: User = Depends(require_admin), event_bus: EventBus = Depends(get_event_bus)):
    """Update config via gateway RPC."""
    # Never allow setting secret fields through the API
    def _has_secret_keys(obj, depth=0):
        if depth > 10:
            return True
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k.lower() in _SECRET_KEY_NAMES:
                    return True
                if _has_secret_keys(v, depth + 1):
                    return True
        elif isinstance(obj, list):
            for item in obj:
                if _has_secret_keys(item, depth + 1):
                    return True
        return False

    if _has_secret_keys(data):
        return JSONResponse({"error": "Cannot set secret fields via API"}, status_code=400)

    try:
        result = await gateway_call("config.set", data)
        if result.get("ok"):
            if event_bus:
                await event_bus.emit("config.updated", "config", details={"keys": list(data.keys())})
            return {"status": "updated"}
        return JSONResponse({"error": result.get("error", "Failed to update config")}, status_code=500)
    except ConnectionError:
        return JSONResponse({"error": "Gateway unavailable"}, status_code=503)
    except Exception as e:
        return JSONResponse({"error": "Internal server error"}, status_code=500)


@router.post("/api/config/apply")
async def apply_config(_admin: User = Depends(require_admin)):
    """Apply config changes via gateway RPC."""
    try:
        result = await gateway_call("config.apply")
        if result.get("ok"):
            return {"status": "applied"}
        return JSONResponse({"error": result.get("error", "Failed to apply config")}, status_code=500)
    except ConnectionError:
        return JSONResponse({"error": "Gateway unavailable"}, status_code=503)
    except Exception as e:
        return JSONResponse({"error": "Internal server error"}, status_code=500)


@router.get("/api/config/models")
async def list_models(_admin: User = Depends(require_admin)):
    """Get available models via gateway RPC."""
    try:
        result = await gateway_call("models.list")
        if result.get("ok"):
            return {"models": result.get("result", {}).get("models", [])}
    except Exception:
        pass
    return {"models": []}


@router.get("/api/models")
async def list_models_alt(_admin: User = Depends(require_admin)):
    """Alias for /api/config/models — available models."""
    try:
        result = await gateway_call("models.list")
        if result.get("ok"):
            return {"models": result.get("result", {}).get("models", [])}
    except Exception:
        pass
    return {"models": []}
