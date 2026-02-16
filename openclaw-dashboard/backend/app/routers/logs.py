"""Log tailing endpoint — aggregates openclaw dir logs + PM2 agent logs."""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from app.config import settings

router = APIRouter(tags=["logs"])

PM2_LOG_DIR = Path.home() / ".pm2" / "logs"


def _collect_log_sources() -> dict[str, Path]:
    """Return a mapping of display-name -> absolute path for every log file."""
    sources: dict[str, Path] = {}

    # 1) Classic openclaw log dir
    logs_dir = settings.openclaw_dir / "logs"
    if logs_dir.is_dir():
        for f in sorted(logs_dir.iterdir()):
            if f.is_file():
                sources[f.name] = f

    # 2) PM2 logs for openclaw processes
    if PM2_LOG_DIR.is_dir():
        for f in sorted(PM2_LOG_DIR.iterdir()):
            if f.is_file() and f.name.startswith("openclaw-"):
                sources[f.name] = f

    return sources


@router.get("/api/logs/files")
async def list_log_files():
    sources = _collect_log_sources()
    files = []
    for name, path in sources.items():
        try:
            stat = path.stat()
            files.append({
                "name": name,
                "size_bytes": stat.st_size,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "modified": stat.st_mtime,
            })
        except OSError:
            pass
    return {"files": files}


@router.get("/api/logs/tail")
async def tail_logs(file: str = "openclaw.log", lines: int = Query(100, le=1000)):
    sources = _collect_log_sources()
    path = sources.get(file)
    if path is None or not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Log file not found. Available: {list(sources.keys())}",
        )

    # Guard against path traversal
    if ".." in file or "/" in file:
        raise HTTPException(status_code=400, detail="Invalid filename")

    try:
        with open(path) as f:
            all_lines = f.readlines()
            recent = all_lines[-lines:]
        return {"file": file, "lines": recent, "total": len(all_lines)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
