"""Authentication endpoints — login, profile, password change, lockout management."""

import time
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.db.connection import get_session
from app.models.database import User
from app.redis.client import get_redis
from app.services.auth import (
    verify_password, hash_password, create_access_token, get_current_user,
)

# Pre-hashed dummy for constant-time login timing (prevents username enumeration)
_DUMMY_HASH = hash_password("__dummy_timing_constant__")

router = APIRouter(prefix="/api/auth", tags=["auth"])

MAX_ATTEMPTS = 3
LOCKOUT_SECONDS = 60 * 60  # 60 minutes
_FAIL_PREFIX = "login_fail:"
_LOCK_PREFIX = "login_lock:"

# In-memory fallback when Redis is unavailable
_mem_fails: dict[str, list[float]] = {}   # ip -> [timestamps]
_mem_locks: dict[str, float] = {}          # ip -> locked_until_ts


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    username: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


def _client_ip(request: Request) -> str:
    """Extract the client IP from the socket connection.

    X-Forwarded-For is intentionally ignored to prevent spoofing.
    If behind a trusted reverse proxy, configure uvicorn's
    ``--proxy-headers`` and ``--forwarded-allow-ips`` instead.
    """
    return request.client.host if request.client else "unknown"


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request, session: AsyncSession = Depends(get_session)):
    redis = get_redis()
    ip = _client_ip(request)
    now_ts = int(datetime.now(timezone.utc).timestamp())

    # Check lockout (Redis or in-memory)
    if redis:
        locked_until = await redis.get(f"{_LOCK_PREFIX}{ip}")
        if locked_until:
            remaining = int(float(locked_until)) - now_ts
            minutes = max(1, remaining // 60)
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"Too many failed attempts. Try again in {minutes} minute{'s' if minutes != 1 else ''}.",
            )
    else:
        lock_ts = _mem_locks.get(ip, 0)
        if lock_ts > now_ts:
            remaining = int(lock_ts) - now_ts
            minutes = max(1, remaining // 60)
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"Too many failed attempts. Try again in {minutes} minute{'s' if minutes != 1 else ''}.",
            )
        elif lock_ts:
            _mem_locks.pop(ip, None)

    result = await session.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    # Always run bcrypt to prevent timing-based username enumeration
    valid = verify_password(body.password, user.hashed_password if user else _DUMMY_HASH) and user is not None
    if not valid:
        # Record failed attempt (Redis or in-memory)
        if redis:
            key = f"{_FAIL_PREFIX}{ip}"
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, LOCKOUT_SECONDS)
            if count >= MAX_ATTEMPTS:
                lock_until = now_ts + LOCKOUT_SECONDS
                await redis.set(f"{_LOCK_PREFIX}{ip}", str(lock_until), ex=LOCKOUT_SECONDS)
                await redis.delete(key)
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail="Too many failed attempts. Try again in 60 minutes.",
                )
        else:
            now_f = time.time()
            cutoff = now_f - LOCKOUT_SECONDS
            fails = _mem_fails.setdefault(ip, [])
            fails = [t for t in fails if t > cutoff]
            fails.append(now_f)
            _mem_fails[ip] = fails
            if len(fails) >= MAX_ATTEMPTS:
                _mem_locks[ip] = now_f + LOCKOUT_SECONDS
                _mem_fails.pop(ip, None)
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail="Too many failed attempts. Try again in 60 minutes.",
                )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Success — clear any failed attempt tracking for this IP
    if redis:
        await redis.delete(f"{_FAIL_PREFIX}{ip}", f"{_LOCK_PREFIX}{ip}")
    else:
        _mem_fails.pop(ip, None)
        _mem_locks.pop(ip, None)
    user.last_login = datetime.now(timezone.utc)
    await session.commit()
    token = create_access_token(user.id)
    return LoginResponse(token=token, username=user.username)


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {
        "id": str(user.id),
        "username": user.username,
        "is_admin": user.is_admin,
        "created_at": user.created_at.isoformat(),
        "last_login": user.last_login.isoformat() if user.last_login else None,
    }


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.hashed_password = hash_password(body.new_password)
    await session.commit()
    return {"message": "Password changed successfully"}


# --- Admin lockout management ---


async def _require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


@router.get("/lockouts")
async def list_lockouts(user: User = Depends(_require_admin)):
    """List all currently locked-out IPs."""
    redis = get_redis()
    if not redis:
        return {"lockouts": []}
    now = int(datetime.now(timezone.utc).timestamp())
    lockouts: List[dict] = []
    async for key in redis.scan_iter(match=f"{_LOCK_PREFIX}*"):
        ip = key[len(_LOCK_PREFIX):]
        locked_until = await redis.get(key)
        if locked_until:
            remaining = int(float(locked_until)) - now
            if remaining > 0:
                lockouts.append({
                    "ip": ip,
                    "minutes_remaining": max(1, remaining // 60),
                    "locked_until": datetime.fromtimestamp(int(float(locked_until)), tz=timezone.utc).isoformat(),
                })
    return {"lockouts": lockouts}


@router.delete("/lockouts/{ip}")
async def unlock_ip(ip: str, user: User = Depends(_require_admin)):
    """Remove a lockout for a specific IP address."""
    redis = get_redis()
    if not redis:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    deleted = await redis.delete(f"{_LOCK_PREFIX}{ip}", f"{_FAIL_PREFIX}{ip}")
    if deleted == 0:
        raise HTTPException(status_code=404, detail="No lockout found for this IP")
    return {"message": f"Lockout cleared for {ip}"}


@router.delete("/lockouts")
async def unlock_all(user: User = Depends(_require_admin)):
    """Clear all login lockouts."""
    redis = get_redis()
    if not redis:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    cleared = 0
    async for key in redis.scan_iter(match=f"{_LOCK_PREFIX}*"):
        await redis.delete(key)
        cleared += 1
    async for key in redis.scan_iter(match=f"{_FAIL_PREFIX}*"):
        await redis.delete(key)
        cleared += 1
    return {"message": f"Cleared {cleared} lockout entries"}
