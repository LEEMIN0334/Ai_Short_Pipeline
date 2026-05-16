from datetime import UTC, datetime, timedelta

import pytest
from ai_shorts.agents.trend_scout import TrendScoutPolicy, curate_trends, run_trend_scout
from ai_shorts.schemas.trend_item import Platform, TrendItem


def _trend(
    source_id: str,
    *,
    views: int | None = 1000,
    likes: int | None = 100,
    comments: int | None = 10,
    shares: int | None = 5,
    published_at: datetime | None = None,
    raw: dict[str, object] | None = None,
) -> TrendItem:
    return TrendItem(
        source_id=source_id,
        platform=Platform.INSTAGRAM,
        url=f"https://example.com/reel/{source_id}",
        view_count=views,
        like_count=likes,
        comment_count=comments,
        share_count=shares,
        published_at=published_at,
        collected_at=datetime(2026, 5, 16, tzinfo=UTC),
        raw=raw or {},
    )


def test_curate_trends_deduplicates_by_source_id() -> None:
    now = datetime(2026, 5, 16, tzinfo=UTC)
    weaker = _trend("same", views=100, likes=5)
    stronger = _trend("same", views=1000, likes=200)

    result = curate_trends([weaker, stronger], now=now)

    assert [item.trend for item in result.selected] == [stronger]
    assert [(item.trend, item.reason) for item in result.rejected] == [
        (weaker, "duplicate_lower_signal")
    ]


def test_curate_trends_filters_low_view_and_stale_items() -> None:
    now = datetime(2026, 5, 16, tzinfo=UTC)
    policy = TrendScoutPolicy(min_views=500, max_age_hours=48)
    fresh = _trend("fresh", views=800, published_at=now - timedelta(hours=2))
    low_view = _trend("low", views=10, published_at=now - timedelta(hours=2))
    stale = _trend("stale", views=800, published_at=now - timedelta(days=10))

    result = curate_trends([fresh, low_view, stale], policy=policy, now=now)

    assert [item.trend.source_id for item in result.selected] == ["fresh"]
    assert {item.reason for item in result.rejected} == {"below_min_views", "stale"}


def test_curate_trends_ranks_and_limits_results() -> None:
    now = datetime(2026, 5, 16, tzinfo=UTC)
    policy = TrendScoutPolicy(max_items=2)
    weak = _trend("weak", views=100, likes=5)
    strong = _trend("strong", views=5000, likes=500)
    medium = _trend("medium", views=900, likes=100)

    result = curate_trends([weak, strong, medium], policy=policy, now=now)

    assert [item.trend.source_id for item in result.selected] == ["strong", "medium"]
    assert result.selected[0].viral_score > result.selected[1].viral_score


def test_curate_trends_uses_category_from_raw_metadata() -> None:
    now = datetime(2026, 5, 16, tzinfo=UTC)
    trend = _trend("cat", raw={"category": "Comedy"})

    result = curate_trends([trend], now=now)

    assert result.selected[0].category == "comedy"


@pytest.mark.asyncio
async def test_run_trend_scout_collects_from_multiple_sources() -> None:
    now = datetime(2026, 5, 16, tzinfo=UTC)

    async def instagram_source() -> list[TrendItem]:
        return [_trend("ig_1", views=500)]

    async def youtube_source() -> list[TrendItem]:
        return [_trend("yt_1", views=1500)]

    run = await run_trend_scout(
        {"instagram": instagram_source, "youtube": youtube_source},
        now=now,
    )

    assert [report.source for report in run.sources] == ["instagram", "youtube"]
    assert [report.items_collected for report in run.sources] == [1, 1]
    assert [item.trend.source_id for item in run.result.selected] == ["yt_1", "ig_1"]


@pytest.mark.asyncio
async def test_run_trend_scout_reports_failed_sources() -> None:
    now = datetime(2026, 5, 16, tzinfo=UTC)

    async def working_source() -> list[TrendItem]:
        return [_trend("ok", views=500)]

    async def failing_source() -> list[TrendItem]:
        msg = "rate limit"
        raise RuntimeError(msg)

    run = await run_trend_scout(
        {"working": working_source, "failing": failing_source},
        now=now,
    )

    assert [item.trend.source_id for item in run.result.selected] == ["ok"]
    assert run.sources[0].error is None
    assert run.sources[1].source == "failing"
    assert run.sources[1].items_collected == 0
    assert run.sources[1].error == "RuntimeError: rate limit"
