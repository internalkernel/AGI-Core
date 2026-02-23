"""Session management endpoints."""

from fastapi import APIRouter
from app.services.job_service import get_sessions_detailed

router = APIRouter(tags=["sessions"])


@router.get("/api/sessions")
async def list_sessions():
    sessions = get_sessions_detailed()
    return {"sessions": sessions, "total": len(sessions)}
