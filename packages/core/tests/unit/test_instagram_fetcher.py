from datetime import UTC, datetime

import pytest
from ai_shorts.adapters.instagram_fetcher import (
    InstagramFetcher,
    InstagramMedia,
    InstagramMediaKind,
    InstagramSessionRequiredError,
)
from ai_shorts.schemas.trend_item import Platform


def test_instagram_media_converts_to_trend_item() -> None:
    media = InstagramMedia(
        source_id="reel_001",
        kind=InstagramMediaKind.REEL,
        url="https://www.instagram.com/reel/example/",
        title="Example reel",
        author="creator",
        view_count=100,
        like_count=10,
        comment_count=2,
        share_count=1,
        raw={"shortcode": "example"},
    )

    trend = media.to_trend_item(collected_at=datetime(2026, 1, 1, tzinfo=UTC))

    assert trend.platform == Platform.INSTAGRAM
    assert trend.source_id == "reel_001"
    assert trend.title == "Example reel"
    assert trend.raw["kind"] == "reel"
    assert trend.raw["shortcode"] == "example"


@pytest.mark.asyncio
async def test_fetch_reel_requires_session() -> None:
    fetcher = InstagramFetcher()

    with pytest.raises(InstagramSessionRequiredError):
        await fetcher.fetch_reel("https://www.instagram.com/reel/example/")
