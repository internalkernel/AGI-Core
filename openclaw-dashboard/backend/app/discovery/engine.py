"""Core discovery engine — ported from agent-console/discover.js to Python.

Scans the OpenClaw workspace for pipelines, agents, skills, cron jobs, and
custom modules. Results are cached and refreshed periodically.

Supports multi-agent setups with separate workspace-* directories per agent.
"""

import json
import re
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from app.config import settings
from app.discovery.patterns import (
    PIPELINE_PATTERNS,
    AGENT_PATTERNS,
    SKILL_CATEGORIES,
    MODULE_TYPES,
)

_cached_result: Dict = {}
_last_discovery = 0.0

WORKSPACE = settings.openclaw_dir / "workspace"


def get_all_workspaces() -> List[Path]:
    """Return all workspace paths: default workspace/ plus any workspace-* dirs."""
    workspaces = []
    if WORKSPACE.exists():
        workspaces.append(WORKSPACE)
    try:
        for p in sorted(settings.openclaw_dir.glob("workspace-*")):
            if p.is_dir():
                workspaces.append(p)
    except Exception:
        pass
    return workspaces


def get_cached_result() -> Dict:
    """Return cached discovery result or empty dict."""
    return _cached_result


def run_discovery() -> Dict:
    """Run full discovery scan. Returns a dict matching DiscoveryResult schema."""
    global _cached_result, _last_discovery

    all_workspaces = get_all_workspaces()

    result = {
        "detected_at": datetime.now().isoformat(),
        "workspace": str(WORKSPACE),
        "workspaces": [str(w) for w in all_workspaces],
        "pipelines": discover_pipelines(),
        "agents": discover_agents(),
        "skills": discover_skills(),
        "custom_modules": discover_custom_modules(),
        "metrics": {},
    }

    result["metrics"] = {
        "pipelines": len(result["pipelines"]),
        "agents": len(result["agents"]),
        "skills": len(result["skills"]),
        "modules": len(result["custom_modules"]),
    }

    _cached_result = result
    _last_discovery = time.time()
    return result


def needs_refresh() -> bool:
    return time.time() - _last_discovery > settings.discovery_interval_seconds


# ---------------------------------------------------------------------------
# Pipeline Discovery
# ---------------------------------------------------------------------------

def discover_pipelines() -> List[Dict]:
    pipelines = []
    seen_ids = set()

    for workspace in get_all_workspaces():
        try:
            for entry in workspace.iterdir():
                if not entry.is_dir():
                    continue
                name_lower = entry.name.lower()

                for key, config in PIPELINE_PATTERNS.items():
                    if key in seen_ids:
                        continue
                    if any(p in name_lower for p in config["patterns"]):
                        stages = _detect_stages(entry)
                        pipelines.append({
                            "id": key,
                            "name": config["name"],
                            "icon": config["icon"],
                            "color": config["color"],
                            "directory": entry.name,
                            "path": str(entry),
                            "stages": stages if stages else config["stages"],
                            "metrics": config["metrics"],
                            "status": _detect_pipeline_status(entry),
                            "source": "filesystem",
                        })
                        seen_ids.add(key)
                        break
        except Exception:
            pass

    # Also check HEARTBEAT.md
    _check_heartbeat(pipelines, seen_ids)

    return pipelines


def _detect_stages(pipeline_path: Path) -> List[str]:
    stages = []
    skip = {"scripts", "src", "output", "logs", "config", "node_modules", ".git", "__pycache__", "venv"}
    try:
        for entry in pipeline_path.iterdir():
            if entry.is_dir() and entry.name.lower() not in skip:
                stages.append(entry.name)
    except Exception:
        pass
    return stages


def _detect_pipeline_status(pipeline_path: Path) -> str:
    try:
        one_hour_ago = time.time() - 3600
        for sub in ["logs", "output"]:
            d = pipeline_path / sub
            if d.exists():
                for f in d.iterdir():
                    if f.stat().st_mtime > one_hour_ago:
                        return "active"
        # Check root-level files
        for f in pipeline_path.iterdir():
            if f.is_file() and f.stat().st_mtime > one_hour_ago:
                return "active"
        return "idle"
    except Exception:
        return "unknown"


def _check_heartbeat(pipelines: List[Dict], seen_ids: set):
    hb = WORKSPACE / "HEARTBEAT.md"
    if not hb.exists():
        return
    try:
        content = hb.read_text()
        for line in content.split("\n"):
            m = re.match(r"^#+\s+(HYDROFLOW|YouTube|Pipeline|Orchestrator|Content|Market)", line, re.IGNORECASE)
            if m:
                name = line.lstrip("#").strip()
                pid = name.lower().replace(" ", "-")
                if pid not in seen_ids:
                    pipelines.append({
                        "id": pid,
                        "name": name,
                        "icon": "clipboard",
                        "color": "#6366f1",
                        "directory": "",
                        "path": "",
                        "stages": [],
                        "metrics": [],
                        "status": "active",
                        "source": "HEARTBEAT.md",
                    })
                    seen_ids.add(pid)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Agent Discovery
# ---------------------------------------------------------------------------

def discover_agents() -> List[Dict]:
    agents = []
    seen = set()

    # Primary: discover agents from workspace-*/config.json files
    for workspace in get_all_workspaces():
        if workspace == WORKSPACE:
            continue  # skip default workspace (docs only)
        config_file = workspace / "config.json"
        if not config_file.exists():
            continue
        try:
            data = json.loads(config_file.read_text())
            if not isinstance(data, dict):
                continue
            agent_name = data.get("name", workspace.name.replace("workspace-", ""))
            if agent_name in seen:
                continue
            seen.add(agent_name)

            # Derive a readable workspace label from the directory name
            workspace_label = workspace.name.replace("workspace-", "")
            atype = _detect_agent_type(workspace_label, data)
            pat = AGENT_PATTERNS.get(atype, AGENT_PATTERNS["general"])

            # Detect status from workspace activity
            status = _detect_agent_status(workspace)

            agents.append({
                "name": agent_name,
                "type": atype,
                "icon": pat["icon"],
                "color": pat["color"],
                "config_path": str(config_file),
                "workspace": str(workspace),
                "workspace_label": workspace_label,
                "port": data.get("port"),
                "model": data.get("model", "unknown"),
                "capabilities": data.get("capabilities", []),
                "source": "workspace_config",
                "status": status,
            })
        except Exception:
            pass

    # Fallback: scan traditional agent config paths within each workspace
    for workspace in get_all_workspaces():
        agent_paths = [
            workspace / "agents",
            workspace / "agent-swarm",
            workspace / "swarm-framework",
            workspace / "hydroflow" / "config",
        ]
        for ap in agent_paths:
            if not ap.exists():
                continue
            try:
                for f in ap.iterdir():
                    if not f.is_file():
                        continue
                    if f.suffix == ".json" or "agent" in f.name.lower():
                        try:
                            data = json.loads(f.read_text())
                            if isinstance(data, dict) and any(k in data for k in ("agents", "agent", "name")):
                                agent_name = data.get("name", f.stem)
                                if agent_name in seen:
                                    continue
                                seen.add(agent_name)
                                atype = _detect_agent_type(f.name, data)
                                pat = AGENT_PATTERNS.get(atype, AGENT_PATTERNS["general"])
                                agents.append({
                                    "name": agent_name,
                                    "type": atype,
                                    "icon": pat["icon"],
                                    "color": pat["color"],
                                    "config_path": str(f),
                                    "capabilities": data.get("capabilities", []),
                                    "source": "config",
                                    "status": "configured",
                                })
                        except (json.JSONDecodeError, Exception):
                            pass
            except Exception:
                pass

    # Discover from active sessions
    _discover_agents_from_sessions(agents, seen)

    return agents


def _detect_agent_type(filename: str, config: dict) -> str:
    name = (config.get("name", "") or filename).lower()
    for atype, pat in AGENT_PATTERNS.items():
        if any(skill in name for skill in pat["skills"]):
            return atype
    # Fallback patterns
    if any(w in name for w in ("code", "dev")):
        return "coder"
    if any(w in name for w in ("research", "investigate")):
        return "researcher"
    if any(w in name for w in ("write", "content")):
        return "writer"
    if any(w in name for w in ("ops", "deploy")):
        return "devops"
    if any(w in name for w in ("admin", "manage")):
        return "admin"
    if any(w in name for w in ("sales", "outreach")):
        return "sales"
    return "general"


def _detect_agent_status(workspace: Path) -> str:
    """Detect agent status from workspace activity (logs, memory.db mtime, agents/)."""
    try:
        one_hour_ago = time.time() - 3600
        # Check memory.db mtime
        mem_db = workspace / "memory.db"
        if mem_db.exists() and mem_db.stat().st_mtime > one_hour_ago:
            return "active"
        # Check logs directory
        logs_dir = workspace / "logs"
        if logs_dir.exists():
            for f in logs_dir.iterdir():
                if f.is_file() and f.stat().st_mtime > one_hour_ago:
                    return "active"
        # Check agents/main directory
        agents_dir = workspace / "agents" / "main"
        if agents_dir.exists():
            for f in agents_dir.rglob("*"):
                if f.is_file() and f.stat().st_mtime > one_hour_ago:
                    return "active"
                break  # only check first file for perf
        return "idle"
    except Exception:
        return "unknown"


def _discover_agents_from_sessions(agents: List[Dict], seen: set):
    try:
        result = subprocess.run(
            ["openclaw", "sessions", "list", "--json"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            sessions = json.loads(result.stdout)
            for s in sessions:
                aid = s.get("agentId", "")
                if aid and aid not in seen:
                    seen.add(aid)
                    agents.append({
                        "name": aid,
                        "type": "general",
                        "icon": "bot",
                        "color": "#6366f1",
                        "config_path": "",
                        "capabilities": [],
                        "source": "active_session",
                        "status": s.get("status", "unknown"),
                    })
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Skill Discovery
# ---------------------------------------------------------------------------

def _parse_skill_frontmatter(skill_dir: Path) -> dict:
    """Parse SKILL.md YAML frontmatter for metadata like disable-model-invocation."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return {}
    try:
        text = skill_md.read_text(encoding="utf-8")[:2000]
        if not text.startswith("---"):
            return {}
        end = text.index("---", 3)
        block = text[3:end]
        meta = {}
        for line in block.strip().split("\n"):
            if ":" in line:
                key, val = line.split(":", 1)
                val = val.strip()
                if val.lower() in ("true", "yes"):
                    val = True
                elif val.lower() in ("false", "no"):
                    val = False
                meta[key.strip()] = val
        return meta
    except Exception:
        return {}


def _load_workspace_skill_configs() -> Dict[str, Dict[str, dict]]:
    """Load skills.entries from each workspace openclaw.json.

    Returns {workspace_label: {skill_name: {enabled: bool, ...}}}
    """
    result: Dict[str, Dict[str, dict]] = {}
    for ws in get_all_workspaces():
        if ws == WORKSPACE:
            continue
        label = ws.name.replace("workspace-", "")
        oc = ws / "openclaw.json"
        if not oc.exists():
            result[label] = {}
            continue
        try:
            data = json.loads(oc.read_text())
            result[label] = data.get("skills", {}).get("entries", {})
        except Exception:
            result[label] = {}
    return result


def discover_skills() -> List[Dict]:
    # Skills are installed at the root level, not inside any workspace
    skills_dir = settings.openclaw_dir / "skills"
    skills = []
    if not skills_dir.exists():
        return skills

    ws_configs = _load_workspace_skill_configs()

    try:
        for entry in sorted(skills_dir.iterdir()):
            if entry.is_dir():
                readme = entry / "README.md"
                desc = ""
                if readme.exists():
                    try:
                        text = readme.read_text()[:500]
                        # First non-empty, non-heading line
                        for ln in text.split("\n"):
                            ln = ln.strip()
                            if ln and not ln.startswith("#"):
                                desc = ln[:200]
                                break
                    except Exception:
                        pass

                fm = _parse_skill_frontmatter(entry)
                on_demand = fm.get("disable-model-invocation", False) is True

                # Build per-agent enablement list
                agents = {}
                for agent_label, entries in ws_configs.items():
                    cfg = entries.get(entry.name, {})
                    if cfg.get("enabled") is False:
                        agents[agent_label] = "disabled"
                    elif on_demand:
                        agents[agent_label] = "on-demand"
                    else:
                        agents[agent_label] = "enabled"

                skills.append({
                    "name": entry.name,
                    "path": str(entry),
                    "category": _categorize_skill(entry.name),
                    "has_readme": readme.exists(),
                    "description": desc,
                    "on_demand": on_demand,
                    "agents": agents,
                })
    except Exception:
        pass

    return skills


def _categorize_skill(name: str) -> str:
    name_lower = name.lower()
    for cat, keywords in SKILL_CATEGORIES.items():
        if any(kw in name_lower for kw in keywords):
            return cat
    return "general"


# ---------------------------------------------------------------------------
# Custom Module Discovery
# ---------------------------------------------------------------------------

def discover_custom_modules() -> List[Dict]:
    modules = []
    seen = set()
    known = [
        "swarmstarter", "solpaw", "clawnch", "hydroflow",
        "deepwork-tracker", "triple-memory",
    ]
    for workspace in get_all_workspaces():
        for mod in known:
            if mod in seen:
                continue
            mod_path = workspace / mod
            if mod_path.exists():
                mtype = "custom"
                for keyword, t in MODULE_TYPES.items():
                    if keyword in mod:
                        mtype = t
                        break
                modules.append({
                    "name": mod,
                    "path": str(mod_path),
                    "type": mtype,
                    "status": "installed",
                })
                seen.add(mod)
    return modules
