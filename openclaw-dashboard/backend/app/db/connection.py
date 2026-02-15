"""Async database engine and session management."""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from app.config import settings

engine = None
async_session_factory = None


async def init_db():
    """Create async engine and all tables."""
    global engine, async_session_factory
    if not settings.database_url:
        return
    engine = create_async_engine(settings.database_url, echo=False, pool_size=5, max_overflow=10)
    async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def close_db():
    """Dispose engine on shutdown."""
    global engine
    if engine:
        await engine.dispose()


async def get_session():
    """FastAPI dependency yielding an async session."""
    if async_session_factory is None:
        raise RuntimeError("Database not initialized")
    async with async_session_factory() as session:
        yield session
