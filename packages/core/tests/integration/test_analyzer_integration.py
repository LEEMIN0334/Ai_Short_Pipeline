from decimal import Decimal

import pytest
from ai_shorts.agents.analyzer import TrendAnalyzer
from ai_shorts.config import get_settings
from ai_shorts.storage.postgres import get_conn


@pytest.mark.asyncio
async def test_analyzer_scores_and_stores_trend_item() -> None:
    if not get_settings().postgres_url:
        pytest.skip("POSTGRES_URL is not configured")

    source_id = "phase1_analyzer_trend_001"
    trend_id: int | None = None

    try:
        async with get_conn() as conn:
            await conn.execute("DELETE FROM trend_item WHERE source_id = $1", source_id)
            trend_id = await conn.fetchval(
                """
                INSERT INTO trend_item (
                    platform, source_id, url, title, author,
                    view_count, like_count, comment_count, share_count, raw
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb)
                RETURNING id
                """,
                "youtube",
                source_id,
                "https://example.com/watch?v=phase1",
                "AI agent trend",
                "creator",
                10_000,
                1_000,
                100,
                50,
                '{"fixture": true}',
            )

        scored = await TrendAnalyzer().score_and_store(trend_id)

        async with get_conn() as conn:
            row = await conn.fetchrow(
                """
                SELECT viral_score, category, reasons
                FROM scored_trend_item
                WHERE trend_item_id = $1
                """,
                trend_id,
            )

        assert scored.category == "ai"
        assert row is not None
        assert Decimal(str(row["viral_score"])) > Decimal("0")
        assert row["category"] == "ai"
    finally:
        if trend_id is not None:
            async with get_conn() as conn:
                await conn.execute("DELETE FROM trend_item WHERE id = $1", trend_id)
