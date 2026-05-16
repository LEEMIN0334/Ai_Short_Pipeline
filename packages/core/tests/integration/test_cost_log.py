from decimal import Decimal

import pytest
from ai_shorts.adapters._stub import StubAdapter
from ai_shorts.config import get_settings
from ai_shorts.observability.cost_log import make_postgres_sink
from ai_shorts.storage.postgres import get_conn


@pytest.mark.asyncio
async def test_cost_event_persists_to_db() -> None:
    if not get_settings().postgres_url:
        pytest.skip("POSTGRES_URL is not configured")

    job_id = "test_cost_log_001"
    sink = make_postgres_sink(job_id=job_id, agent_id="stub_agent")
    adapter = StubAdapter(cost_sink=sink)

    try:
        result = await adapter.do_thing("hi")

        async with get_conn() as conn:
            rows = await conn.fetch(
                """
                SELECT service, operation, usd, metadata->>'input_length' AS input_length
                FROM cost_log
                WHERE job_id = $1
                ORDER BY created_at DESC
                """,
                job_id,
            )

        assert result == "stub-output:hi"
        assert len(rows) == 1
        assert rows[0]["service"] == "stub"
        assert rows[0]["operation"] == "do_thing"
        assert Decimal(str(rows[0]["usd"])) == Decimal("0.001000")
        assert rows[0]["input_length"] == "2"
    finally:
        async with get_conn() as conn:
            await conn.execute("DELETE FROM cost_log WHERE job_id = $1", job_id)
