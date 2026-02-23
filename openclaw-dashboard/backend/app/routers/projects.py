"""Projects API — browse agent project files."""

import os
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Query, HTTPException

from app.config import settings
from app.services.auth import require_admin
from app.models.database import User

router = APIRouter(tags=["projects"])

MAX_DEPTH = 5
MAX_ENTRIES = 500
MAX_FILE_SIZE = 50 * 1024  # 50KB

# Only allow alphanumeric, hyphens, and underscores in agent IDs
_SAFE_AGENT_RE = re.compile(r"^[a-zA-Z0-9_-]+$")

# Allowlist of file extensions safe for preview (strict allowlist > denylist)
_ALLOWED_TEXT_EXTENSIONS = {
    ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".csv",
    ".html", ".css", ".js", ".ts", ".py", ".sh", ".xml",
}


def _projects_dir(agent_id: str) -> Path:
    if not _SAFE_AGENT_RE.match(agent_id):
        raise HTTPException(status_code=400, detail="Invalid agent ID")
    return settings.openclaw_dir / f"workspace-{agent_id}" / "projects"


def _validate_agent(agent_id: str) -> Path:
    projects = _projects_dir(agent_id)
    workspace = projects.parent
    if not workspace.exists():
        raise HTTPException(status_code=404, detail=f"Agent workspace not found: {agent_id}")
    return projects


def _safe_resolve(base: Path, relative: str) -> Path:
    """Resolve a relative path and ensure it stays within the base directory."""
    base_resolved = base.resolve()
    resolved = (base / relative).resolve()
    if not resolved.is_relative_to(base_resolved):
        raise HTTPException(status_code=403, detail="Path traversal not allowed")
    if resolved.is_symlink():
        real = resolved.resolve(strict=True)
        if not real.is_relative_to(base_resolved):
            raise HTTPException(status_code=403, detail="Symlink escapes base directory")
    return resolved


def _build_tree(path: Path, depth: int = 0, counter: list | None = None) -> dict:
    if counter is None:
        counter = [0]
    name = path.name
    if path.is_file():
        counter[0] += 1
        return {
            "name": name,
            "type": "file",
            "size": path.stat().st_size,
            "is_markdown": name.lower().endswith(".md"),
        }
    children = []
    if depth < MAX_DEPTH:
        try:
            entries = sorted(path.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
        except PermissionError:
            entries = []
        for entry in entries:
            if entry.name.startswith("."):
                continue
            if counter[0] >= MAX_ENTRIES:
                break
            children.append(_build_tree(entry, depth + 1, counter))
    return {"name": name, "type": "directory", "children": children}


@router.get("/api/projects")
async def list_projects(agent: str = Query(..., description="Agent ID"), _admin: User = Depends(require_admin)):
    projects = _validate_agent(agent)
    if not projects.exists():
        return {"agent": agent, "projects": []}

    result = []
    try:
        entries = sorted(projects.iterdir(), key=lambda e: e.name.lower())
    except PermissionError:
        return {"agent": agent, "projects": []}

    for entry in entries:
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        file_count = 0
        last_mod = 0.0
        for root, dirs, files in os.walk(entry):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in files:
                if not f.startswith("."):
                    file_count += 1
                    fp = os.path.join(root, f)
                    try:
                        mt = os.path.getmtime(fp)
                        if mt > last_mod:
                            last_mod = mt
                    except OSError:
                        pass

        result.append({
            "name": entry.name,
            "file_count": file_count,
            "last_modified": datetime.fromtimestamp(last_mod, tz=timezone.utc).isoformat() if last_mod else None,
            "path": entry.name,
        })

    return {"agent": agent, "projects": result}


@router.get("/api/projects/{agent_id}/{project_name}/tree")
async def project_tree(agent_id: str, project_name: str, _admin: User = Depends(require_admin)):
    projects = _validate_agent(agent_id)
    project_path = _safe_resolve(projects, project_name)
    if not project_path.exists() or not project_path.is_dir():
        raise HTTPException(status_code=404, detail="Project not found")
    return _build_tree(project_path)


@router.get("/api/projects/{agent_id}/file")
async def read_file(agent_id: str, path: str = Query(..., description="Relative path within projects/"), _admin: User = Depends(require_admin)):
    projects = _validate_agent(agent_id)
    file_path = _safe_resolve(projects, path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    # Block dotfiles
    if file_path.name.startswith("."):
        raise HTTPException(status_code=403, detail="Access denied")

    stat = file_path.stat()
    name = file_path.name

    # Strict allowlist — only serve known-safe text extensions
    ext = Path(name).suffix.lower()
    if ext not in _ALLOWED_TEXT_EXTENSIONS:
        return {"name": name, "content": None, "size": stat.st_size, "binary": True}

    if stat.st_size > MAX_FILE_SIZE:
        return {"name": name, "content": None, "size": stat.st_size, "too_large": True}

    try:
        content = file_path.read_text(errors="replace")
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to read file")

    return {"name": name, "content": content, "size": stat.st_size}
