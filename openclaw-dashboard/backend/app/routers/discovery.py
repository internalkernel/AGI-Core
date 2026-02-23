"""Discovery API — pipelines, agents, skills."""

import json
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Query

from app.config import settings
from app.discovery.engine import run_discovery, get_cached_result, discover_skills
from app.services.auth import require_admin
from app.models.database import User

router = APIRouter(tags=["discovery"])

# Keys that expose internal filesystem paths
_PATH_KEYS = {"path", "workspace", "config_path", "workspace_label"}


def _strip_paths(items: list[dict]) -> list[dict]:
    """Return copies of dicts with internal filesystem paths removed."""
    return [{k: v for k, v in item.items() if k not in _PATH_KEYS} for item in items]


@router.get("/api/discovery")
async def full_discovery(_admin: User = Depends(require_admin)):
    result = get_cached_result()
    if not result:
        result = run_discovery()
    # Strip top-level filesystem paths even for admin (not operationally needed)
    safe = {k: v for k, v in result.items() if k not in ("workspace", "workspaces")}
    safe["pipelines"] = _strip_paths(safe.get("pipelines", []))
    safe["agents"] = _strip_paths(safe.get("agents", []))
    safe["skills"] = _strip_paths(safe.get("skills", []))
    return safe


@router.post("/api/discovery/refresh")
async def refresh_discovery(_admin: User = Depends(require_admin)):
    result = run_discovery()
    return {"status": "refreshed", "metrics": result.get("metrics", {})}


@router.get("/api/pipelines")
async def list_pipelines():
    result = get_cached_result()
    if not result:
        result = run_discovery()
    pipelines = _strip_paths(result.get("pipelines", []))
    return {"pipelines": pipelines, "total": len(pipelines)}


@router.get("/api/pipelines/{pipeline_id}")
async def get_pipeline(pipeline_id: str):
    result = get_cached_result()
    if not result:
        result = run_discovery()
    for p in result.get("pipelines", []):
        if p["id"] == pipeline_id:
            return {k: v for k, v in p.items() if k not in _PATH_KEYS}
    return {"error": "Pipeline not found"}


@router.get("/api/agents")
async def list_agents():
    result = get_cached_result()
    if not result:
        result = run_discovery()
    agents = _strip_paths(result.get("agents", []))
    return {"agents": agents, "total": len(agents)}


@router.get("/api/agents/{agent_name}")
async def get_agent_detail(agent_name: str, _admin: User = Depends(require_admin)):
    """Get extended agent info: identity, workspace config, tools, gateway status."""
    result = get_cached_result()
    if not result:
        result = run_discovery()

    agent = None
    for a in result.get("agents", []):
        if a["name"] == agent_name:
            agent = dict(a)
            break
    if not agent:
        return {"error": "Agent not found"}

    workspace_path = agent.get("workspace")
    if workspace_path:
        ws = Path(workspace_path)

        # Read IDENTITY.md
        identity_file = ws / "IDENTITY.md"
        if identity_file.exists():
            try:
                agent["identity"] = identity_file.read_text()[:2000]
            except Exception:
                agent["identity"] = None
        else:
            agent["identity"] = None

        # Read config.json as workspace_config (redact secrets recursively)
        config_file = ws / "config.json"
        if config_file.exists():
            try:
                from app.routers.config import _redact_secrets
                raw_config = json.loads(config_file.read_text())
                agent["workspace_config"] = _redact_secrets(raw_config)
            except Exception:
                agent["workspace_config"] = None
        else:
            agent["workspace_config"] = None

        # Check gateway availability
        port = agent.get("port")
        if port:
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    resp = await client.get(f"http://127.0.0.1:{port}/health")
                    agent["gateway_available"] = resp.status_code == 200
            except Exception:
                agent["gateway_available"] = False
        else:
            agent["gateway_available"] = None
    else:
        agent["identity"] = None
        agent["workspace_config"] = None
        agent["gateway_available"] = None

    # List shared skills
    skills = discover_skills()
    agent["tools"] = [{"name": s["name"], "category": s["category"]} for s in skills]

    # Strip internal filesystem paths before returning
    for key in _PATH_KEYS:
        agent.pop(key, None)

    return agent


@router.get("/api/skills")
async def list_skills(
    category: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    result = get_cached_result()
    if not result:
        result = run_discovery()
    skills = result.get("skills", [])

    if category:
        skills = [s for s in skills if s["category"] == category]
    if search:
        q = search.lower()
        skills = [s for s in skills if q in s["name"].lower() or q in s.get("description", "").lower()]

    total = len(skills)
    start = (page - 1) * limit
    page_skills = _strip_paths(skills[start : start + limit])

    return {"skills": page_skills, "total": total, "page": page, "limit": limit}


@router.get("/api/skills/categories")
async def skill_categories():
    result = get_cached_result()
    if not result:
        result = run_discovery()
    skills = result.get("skills", [])
    cats: dict = {}
    for s in skills:
        c = s.get("category", "general")
        cats[c] = cats.get(c, 0) + 1
    return {"categories": [{"name": k, "count": v} for k, v in sorted(cats.items(), key=lambda x: -x[1])]}


@router.get("/api/skills/{skill_name}")
async def get_skill_detail(skill_name: str):
    result = get_cached_result()
    if not result:
        result = run_discovery()
    for s in result.get("skills", []):
        if s["name"] == skill_name:
            detail = dict(s)
            # Try to read README (using internal path before stripping)
            skill_path = s.get("path")
            if skill_path:
                from pathlib import Path
                readme = Path(skill_path) / "README.md"
                if readme.exists():
                    try:
                        detail["readme"] = readme.read_text()[:5000]
                    except Exception:
                        pass
            # Strip internal filesystem paths
            for key in _PATH_KEYS:
                detail.pop(key, None)
            return detail
    return {"error": "Skill not found"}
