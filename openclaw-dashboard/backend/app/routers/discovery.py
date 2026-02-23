"""Discovery API — pipelines, agents, skills."""

import json
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, Query

from app.config import settings
from app.discovery.engine import run_discovery, get_cached_result, discover_skills

router = APIRouter(tags=["discovery"])


@router.get("/api/discovery")
async def full_discovery():
    result = get_cached_result()
    if not result:
        result = run_discovery()
    return result


@router.post("/api/discovery/refresh")
async def refresh_discovery():
    result = run_discovery()
    return {"status": "refreshed", "metrics": result.get("metrics", {})}


@router.get("/api/pipelines")
async def list_pipelines():
    result = get_cached_result()
    if not result:
        result = run_discovery()
    return {"pipelines": result.get("pipelines", []), "total": len(result.get("pipelines", []))}


@router.get("/api/pipelines/{pipeline_id}")
async def get_pipeline(pipeline_id: str):
    result = get_cached_result()
    if not result:
        result = run_discovery()
    for p in result.get("pipelines", []):
        if p["id"] == pipeline_id:
            return p
    return {"error": "Pipeline not found"}


@router.get("/api/agents")
async def list_agents():
    result = get_cached_result()
    if not result:
        result = run_discovery()
    return {"agents": result.get("agents", []), "total": len(result.get("agents", []))}


@router.get("/api/agents/{agent_name}")
async def get_agent_detail(agent_name: str):
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
    page_skills = skills[start : start + limit]

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
            # Try to read README
            from pathlib import Path
            readme = Path(s["path"]) / "README.md"
            if readme.exists():
                try:
                    detail["readme"] = readme.read_text()[:5000]
                except Exception:
                    pass
            return detail
    return {"error": "Skill not found"}
