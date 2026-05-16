from decimal import Decimal

import pytest
from ai_shorts.config import get_settings
from ai_shorts.storage.postgres import get_conn


@pytest.mark.asyncio
async def test_phase1_collection_tables_round_trip() -> None:
    if not get_settings().postgres_url:
        pytest.skip("POSTGRES_URL is not configured")

    source_id = "phase1_schema_reel_001"
    report_title = "Phase 1 schema research smoke"

    async with get_conn() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                DELETE FROM scored_trend_item
                WHERE trend_item_id IN (
                    SELECT id FROM trend_item WHERE source_id = $1
                )
                """,
                source_id,
            )
            await conn.execute("DELETE FROM trend_item WHERE source_id = $1", source_id)
            await conn.execute("DELETE FROM research_report WHERE title = $1", report_title)

            trend_id = await conn.fetchval(
                """
                INSERT INTO trend_item (
                    platform, source_id, url, title, author,
                    view_count, like_count, comment_count, share_count, raw
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb)
                RETURNING id
                """,
                "instagram",
                source_id,
                "https://example.com/reel/phase1",
                "Schema smoke reel",
                "tester",
                1000,
                100,
                10,
                5,
                '{"fixture": true}',
            )

            await conn.execute(
                """
                INSERT INTO scored_trend_item (trend_item_id, viral_score, category, reasons)
                VALUES ($1, $2, $3, $4::jsonb)
                """,
                trend_id,
                Decimal("12.5"),
                "education",
                '["high engagement"]',
            )

            score_row = await conn.fetchrow(
                """
                SELECT t.source_id, s.viral_score, s.category
                FROM trend_item t
                JOIN scored_trend_item s ON s.trend_item_id = t.id
                WHERE t.source_id = $1
                """,
                source_id,
            )

            report_id = await conn.fetchval(
                """
                INSERT INTO research_report (title, summary, body_markdown, sources)
                VALUES ($1, $2, $3, $4::jsonb)
                RETURNING id
                """,
                report_title,
                "Supabase full text smoke",
                "This report mentions collection schema validation.",
                '[{"title": "source", "url": "https://example.com"}]',
            )

            search_count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM research_report
                WHERE search_vector @@ plainto_tsquery('simple', $1)
                  AND id = $2
                """,
                "collection schema",
                report_id,
            )

            await conn.execute("DELETE FROM scored_trend_item WHERE trend_item_id = $1", trend_id)
            await conn.execute("DELETE FROM trend_item WHERE id = $1", trend_id)
            await conn.execute("DELETE FROM research_report WHERE id = $1", report_id)

    assert score_row is not None
    assert score_row["source_id"] == source_id
    assert Decimal(str(score_row["viral_score"])) == Decimal("12.500000")
    assert score_row["category"] == "education"
    assert search_count == 1
