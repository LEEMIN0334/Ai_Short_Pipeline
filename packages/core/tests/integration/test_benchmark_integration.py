import pytest
from ai_shorts.agents.benchmark import BenchmarkAgent
from ai_shorts.config import get_settings
from ai_shorts.storage.postgres import get_conn


@pytest.mark.asyncio
async def test_benchmark_agent_stores_template() -> None:
    if not get_settings().postgres_url:
        pytest.skip("POSTGRES_URL is not configured")

    source_id = "phase1_benchmark_trend_001"
    trend_id: int | None = None

    try:
        async with get_conn() as conn:
            await conn.execute("DELETE FROM trend_item WHERE source_id = $1", source_id)
            trend_id = await conn.fetchval(
                """
                INSERT INTO trend_item (
                    platform, source_id, url, title, author,
                    view_count, like_count, comment_count, share_count,
                    duration_ms, raw
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb)
                RETURNING id
                """,
                "youtube",
                source_id,
                "https://example.com/watch?v=benchmark",
                "AI benchmark trend",
                "creator",
                50_000,
                5_000,
                300,
                100,
                30_000,
                '{"fixture": true}',
            )

        template = await BenchmarkAgent().build_and_store(trend_id)

        async with get_conn() as conn:
            row = await conn.fetchrow(
                """
                SELECT title, category, duration_ms, scenes
                FROM benchmark_template
                WHERE trend_item_id = $1
                ORDER BY created_at DESC
                LIMIT 1
                """,
                trend_id,
            )

        assert template.category == "ai"
        assert row is not None
        assert row["title"] == "AI benchmark trend"
        assert row["category"] == "ai"
        assert row["duration_ms"] == 30_000
        assert row["scenes"]
    finally:
        if trend_id is not None:
            async with get_conn() as conn:
                await conn.execute("DELETE FROM trend_item WHERE id = $1", trend_id)
