from datetime import UTC, datetime

from ai_shorts.schemas.trend_item import Platform, TrendItem


def test_trend_item_contract_accepts_minimal_payload() -> None:
    item = TrendItem(
        source_id="ig_001",
        platform=Platform.INSTAGRAM,
        url="https://example.com/reel/1",
        collected_at=datetime.now(UTC),
    )

    assert item.platform == Platform.INSTAGRAM
    assert str(item.url).startswith("https://example.com")
