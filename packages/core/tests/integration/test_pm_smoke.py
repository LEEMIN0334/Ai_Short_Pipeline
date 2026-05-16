from decimal import Decimal

import pytest
from ai_shorts.agents.pm.conversational import handle_message
from ai_shorts.config import get_settings
from ai_shorts.storage.postgres import get_conn


@pytest.mark.asyncio
async def test_pm_handles_ping_and_records_cost() -> None:
    if not get_settings().postgres_url:
        pytest.skip("POSTGRES_URL is not configured")

    thread_id = "test_pm_smoke_001"

    try:
        result = await handle_message(thread_id, "ping")

        async with get_conn() as conn:
            rows = await conn.fetch(
                """
                SELECT agent_id, service, operation, usd
                FROM cost_log
                WHERE job_id = $1
                ORDER BY created_at DESC
                """,
                thread_id,
            )

        assert result == "pong (via stub-output:ping)"
        assert len(rows) == 1
        assert rows[0]["agent_id"] == "pm"
        assert rows[0]["service"] == "stub"
        assert rows[0]["operation"] == "do_thing"
        assert Decimal(str(rows[0]["usd"])) == Decimal("0.001000")
    finally:
        async with get_conn() as conn:
            await conn.execute("DELETE FROM cost_log WHERE job_id = $1", thread_id)
