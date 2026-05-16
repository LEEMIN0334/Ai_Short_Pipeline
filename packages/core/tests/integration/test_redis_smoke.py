import pytest
from ai_shorts.storage.redis_client import get_redis
from redis.exceptions import RedisError


@pytest.mark.asyncio
async def test_redis_connection_smoke() -> None:
    try:
        async with get_redis() as redis:
            pong = await redis.ping()
    except RedisError as exc:
        pytest.skip(f"Redis is not available: {exc}")

    assert pong is True
