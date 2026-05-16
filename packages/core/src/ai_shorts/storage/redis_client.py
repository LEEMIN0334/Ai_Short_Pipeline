from typing import cast

from redis.asyncio import Redis

from ai_shorts.config import get_settings


def get_redis_client() -> Redis:
    """Create an async Redis client from REDIS_URL."""

    settings = get_settings()
    return cast(Redis, Redis.from_url(settings.redis_url, decode_responses=True))
