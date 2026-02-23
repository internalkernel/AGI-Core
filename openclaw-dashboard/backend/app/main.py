"""OpenClaw Dashboard — Unified FastAPI application."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from app.config import settings
from app.discovery.engine import run_discovery, needs_refresh
from app.websocket.manager import manager
from app.middleware.security import SecurityHeadersMiddleware, RequestSizeLimitMiddleware, RateLimitMiddleware
from app.db.connection import init_db, close_db, async_session_factory
from app.redis.client import init_redis, close_redis
from app.services.auth import seed_admin, decode_token, authenticate_websocket
from app.routers import (
    overview, jobs, metrics, system, sessions, chat, logs, discovery, channels,
)
from app.routers import config as config_router
from app.routers import nodes, debug, sessions_mgmt
from app.routers import auth as auth_router
from app.routers import activity as activity_router
from app.routers import webhook as webhook_router
from app.routers import calendar as calendar_router
from app.routers import search as search_router
from app.routers import projects as projects_router


async def _discovery_loop():
    while True:
        await asyncio.sleep(settings.discovery_interval_seconds)
        try:
            if needs_refresh():
                run_discovery()
        except Exception:
            pass


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup
    await init_db()
    await init_redis()

    # Seed admin user
    if async_session_factory:
        async with async_session_factory() as session:
            await seed_admin(session)

    run_discovery()
    task = asyncio.create_task(_discovery_loop())

    yield

    # Shutdown
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await close_redis()
    await close_db()


app = FastAPI(
    title="OpenClaw Dashboard",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.enable_docs else None,
    openapi_url="/openapi.json" if settings.enable_docs else None,
    redoc_url=None,
)

# Security middleware (outermost = processes first)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=120)
app.add_middleware(RequestSizeLimitMiddleware, max_size=2_097_152)  # 2MB
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8765",
        "http://127.0.0.1:8765",
        f"http://{settings.host}:8765" if settings.host != "0.0.0.0" else "http://localhost:8765",
        *[o.strip() for o in settings.allowed_origins.split(",") if o.strip()],
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth-exempt paths
AUTH_EXEMPT = {"/api/auth/login", "/api/system/health", "/api/webhook/activity"}
AUTH_EXEMPT_PREFIXES = ("/assets/",)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    # Skip auth for non-API routes, exempt paths, and static files
    if (
        not path.startswith("/api/")
        or path in AUTH_EXEMPT
        or any(path.startswith(p) for p in AUTH_EXEMPT_PREFIXES)
    ):
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        user_id = decode_token(token)
        if user_id and async_session_factory:
            # Verify user still exists in the database
            import uuid
            from sqlmodel import select
            from app.models.database import User
            async with async_session_factory() as session:
                result = await session.execute(
                    select(User.id).where(User.id == uuid.UUID(user_id))
                )
                if result.scalar_one_or_none() is not None:
                    return await call_next(request)

    return JSONResponse(status_code=401, content={"detail": "Not authenticated"})


# Mount all routers
app.include_router(auth_router.router)
app.include_router(activity_router.router)
app.include_router(webhook_router.router)
app.include_router(calendar_router.router)
app.include_router(search_router.router)
app.include_router(overview.router)
app.include_router(jobs.router)
app.include_router(metrics.router)
app.include_router(system.router)
app.include_router(sessions.router)
app.include_router(chat.router)
app.include_router(logs.router)
app.include_router(discovery.router)
app.include_router(config_router.router)
app.include_router(nodes.router)
app.include_router(debug.router)
app.include_router(sessions_mgmt.router)
app.include_router(channels.router)
app.include_router(projects_router.router)


# WebSocket for real-time overview updates
@app.websocket("/ws/realtime")
async def websocket_endpoint(websocket: WebSocket):
    user_id = await authenticate_websocket(websocket)
    if not user_id:
        return
    connected = await manager.connect(websocket, "realtime", accepted=True)
    if not connected:
        return
    try:
        while True:
            await websocket.receive_text()
            if not manager.check_rate(websocket):
                await websocket.send_json({"error": "Rate limit exceeded"})
                continue
            ov = await overview.get_overview()
            await websocket.send_json({"type": "overview", "data": ov.dict()})
    except WebSocketDisconnect:
        manager.disconnect(websocket, "realtime")


# WebSocket for activity stream
@app.websocket("/ws/activity")
async def activity_ws(websocket: WebSocket):
    user_id = await authenticate_websocket(websocket)
    if not user_id:
        return
    connected = await manager.connect(websocket, "activity", accepted=True)
    if not connected:
        return
    try:
        while True:
            await websocket.receive_text()  # keep-alive
            if not manager.check_rate(websocket):
                await websocket.send_json({"error": "Rate limit exceeded"})
                continue
    except WebSocketDisconnect:
        manager.disconnect(websocket, "activity")


# Frontend static files + SPA fallback
frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"

if frontend_dist.exists():
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/")
    async def serve_root():
        return FileResponse(frontend_dist / "index.html")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        if full_path.startswith(("api/", "ws/", "health", "docs", "openapi")):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        fp = (frontend_dist / full_path).resolve()
        if not fp.is_relative_to(frontend_dist.resolve()):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        if fp.exists() and fp.is_file():
            return FileResponse(fp)
        return FileResponse(frontend_dist / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level)
