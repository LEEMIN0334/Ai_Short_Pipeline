from decimal import Decimal

import pytest
from ai_shorts.agents.pm.conversational import handle_message
from ai_shorts.config import get_settings
from ai_shorts.storage.postgres import get_conn


@pytest.mark.asyncio
async def test_pm_ping_records_cost_log() -> None:
    if not get_settings().postgres_url:
        pytest.skip("POSTGRES_URL is not configured")

    job_id = "smoke_test_pm_ping"

    async with get_conn() as conn:
        await conn.execute("DELETE FROM cost_log WHERE job_id = $1", job_id)

    result = await handle_message(job_id, "ping")

    async with get_conn() as conn:
        row = await conn.fetchrow(
            """
            SELECT job_id, agent_id, service, operation, usd
            FROM cost_log
            WHERE job_id = $1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            job_id,
        )
        await conn.execute("DELETE FROM cost_log WHERE job_id = $1", job_id)

    assert result == "pong (via stub-output:ping)"
    assert row is not None
    assert row["job_id"] == job_id
    assert row["agent_id"] == "pm"
    assert row["service"] == "stub"
    assert row["operation"] == "do_thing"
    assert row["usd"] == Decimal("0.001")
