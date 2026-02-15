"""Async Redis client for caching and pub/sub."""

import redis.asyncio as aioredis

from app.config import settings

_redis_client: aioredis.Redis | None = None


async def init_redis():
    """Create global Redis connection."""
    global _redis_client
    if not settings.redis_url:
        return
    _redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    await _redis_client.ping()


async def close_redis():
    """Close Redis connection on shutdown."""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None


def get_redis() -> aioredis.Redis | None:
    """Return the Redis client instance."""
    return _redis_client
