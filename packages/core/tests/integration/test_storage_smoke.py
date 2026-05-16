import pytest
from ai_shorts.config import get_settings
from ai_shorts.storage.postgres import get_conn


@pytest.mark.asyncio
async def test_postgres_connection_smoke() -> None:
    if not get_settings().postgres_url:
        pytest.skip("POSTGRES_URL is not configured")

    async with get_conn() as conn:
        value = await conn.fetchval("SELECT 1")

    assert value == 1
