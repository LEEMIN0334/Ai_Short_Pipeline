import os

import pytest
from ai_shorts.storage.redis_client import get_redis_client


@pytest.mark.asyncio
async def test_redis_ping_smoke() -> None:
    if "REDIS_URL" not in os.environ:
        pytest.skip("REDIS_URL is not configured")

    client = get_redis_client()
    try:
        assert await client.ping() is True
    finally:
        await client.aclose()
