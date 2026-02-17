"""Dashboard overview endpoint."""

import logging
from datetime import datetime
from fastapi import APIRouter
from app.models.schemas import DashboardOverview
from app.services.job_service import get_cron_jobs_raw, get_session_count

router = APIRouter(tags=["overview"])
logger = logging.getLogger("overview")


@router.get("/api/overview", response_model=DashboardOverview)
async def get_overview():
    jobs_data = get_cron_jobs_raw()
    jobs = jobs_data.get("jobs", [])

    total_jobs = len(jobs)
    active_jobs = sum(1 for j in jobs if j.get("enabled", False))
    error_jobs = sum(1 for j in jobs if j.get("state", {}).get("lastStatus") == "error")

    # Pull token usage from gateway RPC (same source as /api/metrics)
    tokens_today = 0
    cost_today = 0.0
    try:
        from app.routers.metrics import _gather_rpc_usage
        rpc = await _gather_rpc_usage()
        tokens_today = rpc["totals"]["totalTokens"]
        cost_today = rpc["totals"]["totalCost"]
    except Exception as e:
        logger.debug("RPC usage unavailable for overview: %s", e)

    uptime = ((total_jobs - error_jobs) / total_jobs * 100) if total_jobs > 0 else 100.0

    # Discovery counts (lazy import to avoid circular)
    from app.discovery.engine import get_cached_result
    disc = get_cached_result()

    return DashboardOverview(
        total_jobs=total_jobs,
        active_jobs=active_jobs,
        error_jobs=error_jobs,
        tokens_today=tokens_today,
        cost_today=round(cost_today, 2),
        uptime_percent=round(uptime, 1),
        active_sessions=get_session_count(),
        last_updated=datetime.now().isoformat(),
        pipelines_count=len(disc.get("pipelines", [])),
        agents_count=len(disc.get("agents", [])),
        skills_count=len(disc.get("skills", [])),
    )
