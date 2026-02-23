"""Session management endpoints."""

from fastapi import APIRouter, Depends
from app.services.job_service import get_sessions_detailed
from app.services.auth import require_admin
from app.models.database import User

router = APIRouter(tags=["sessions"])


@router.get("/api/sessions")
async def list_sessions(_admin: User = Depends(require_admin)):
    sessions = get_sessions_detailed()
    return {"sessions": sessions, "total": len(sessions)}
