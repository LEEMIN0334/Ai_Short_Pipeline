from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from redis.asyncio import Redis

from ai_shorts.config import get_settings


@asynccontextmanager
async def get_redis() -> AsyncIterator[Redis]:
    """Open a short-lived Redis client from REDIS_URL."""

    settings = get_settings()
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()
