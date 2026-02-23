"""Authentication service — JWT tokens and password hashing."""

from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

from fastapi import Depends, HTTPException, WebSocket, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.config import settings
from app.db.connection import get_session
from app.models.database import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        return payload.get("sub")
    except JWTError:
        return None


def _ws_allowed_origins() -> set[str]:
    """Build the set of allowed WebSocket origins from settings."""
    origins = {"http://localhost:8765", "http://127.0.0.1:8765", "https://localhost:8765"}
    host = settings.host
    if host and host != "0.0.0.0":
        origins.add(f"http://{host}:8765")
        origins.add(f"https://{host}:8765")
    for o in settings.allowed_origins.split(","):
        o = o.strip()
        if o:
            origins.add(o)
    return origins


async def authenticate_websocket(websocket: WebSocket) -> Optional[str]:
    """Validate JWT on a WebSocket handshake and accept or reject.

    The token is read from the ``token`` query parameter.  Returns the
    user-id string on success (after accepting the connection) or *None*
    after closing the socket with 1008 (Policy Violation).
    """
    # Origin validation (CSWSH protection)
    origin = websocket.headers.get("origin", "")
    if origin and origin not in _ws_allowed_origins():
        await websocket.close(code=1008, reason="Origin not allowed")
        return None

    from app.db.connection import async_session_factory
    token = websocket.query_params.get("token")
    if token:
        user_id = decode_token(token)
        if user_id and async_session_factory:
            # Verify user still exists in the database
            async with async_session_factory() as session:
                result = await session.execute(
                    select(User).where(User.id == uuid.UUID(user_id))
                )
                if result.scalar_one_or_none() is not None:
                    await websocket.accept()
                    return user_id
    await websocket.close(code=1008, reason="Authentication required")
    return None


async def authenticate_websocket_admin(websocket: WebSocket) -> Optional[str]:
    """Like authenticate_websocket but also enforces admin role.

    Returns user-id on success, *None* after closing with 1008.
    """
    # Origin validation (CSWSH protection)
    origin = websocket.headers.get("origin", "")
    if origin and origin not in _ws_allowed_origins():
        await websocket.close(code=1008, reason="Origin not allowed")
        return None

    from app.db.connection import async_session_factory
    token = websocket.query_params.get("token")
    if token:
        user_id = decode_token(token)
        if user_id and async_session_factory:
            async with async_session_factory() as session:
                result = await session.execute(
                    select(User).where(User.id == uuid.UUID(user_id))
                )
                user = result.scalar_one_or_none()
                if user is not None and user.is_admin:
                    await websocket.accept()
                    return user_id
    await websocket.close(code=1008, reason="Admin access required")
    return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user_id = decode_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    result = await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Dependency that enforces admin access."""
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


async def seed_admin(session: AsyncSession):
    """Create admin user on first run if no users exist."""
    from app.config import _INSECURE_PASSWORDS
    result = await session.execute(select(User).limit(1))
    if result.scalar_one_or_none() is None:
        if settings.admin_password in _INSECURE_PASSWORDS:
            import logging
            logging.getLogger("openclaw.auth").warning(
                "Skipping admin seed — OPENCLAW_DASH_ADMIN_PASSWORD is insecure. "
                "Set a strong password in .env and restart to create the admin user."
            )
            return
        admin = User(
            username="admin",
            hashed_password=hash_password(settings.admin_password),
            is_admin=True,
        )
        session.add(admin)
        await session.commit()
