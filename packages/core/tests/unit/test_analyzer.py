from datetime import UTC, datetime, timedelta

from ai_shorts.agents.analyzer import calculate_viral_score, classify_category
from ai_shorts.schemas.trend_item import Platform, TrendItem


def _trend(**overrides: object) -> TrendItem:
    data: dict[str, object] = {
        "source_id": "trend_001",
        "platform": Platform.YOUTUBE,
        "url": "https://example.com/watch?v=1",
        "title": "AI automation guide",
        "author": "creator",
        "view_count": 10_000,
        "like_count": 1_000,
        "comment_count": 100,
        "share_count": 50,
        "published_at": datetime(2026, 5, 15, tzinfo=UTC),
        "collected_at": datetime(2026, 5, 16, tzinfo=UTC),
        "raw": {},
    }
    data.update(overrides)
    return TrendItem.model_validate(data)


def test_calculate_viral_score_rewards_engagement_and_recency() -> None:
    now = datetime(2026, 5, 16, tzinfo=UTC)
    fresh = _trend(published_at=now - timedelta(hours=1))
    old = _trend(published_at=now - timedelta(days=30))

    assert calculate_viral_score(fresh, now=now) > calculate_viral_score(old, now=now)


def test_classify_category() -> None:
    assert classify_category(_trend(title="ChatGPT agent workflow")) == "ai"
    assert classify_category(_trend(title="How to learn editing")) == "education"
    assert classify_category(_trend(title="A quiet daily vlog", raw={})) == "general"
