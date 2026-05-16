from datetime import UTC

import pytest
from ai_shorts.adapters.youtube_data import (
    YouTubeApiKeyMissingError,
    YouTubeDataAdapter,
    YouTubeQuota,
    YouTubeQuotaExceededError,
    calculate_outlier_score,
    parse_youtube_video,
)
from ai_shorts.schemas.trend_item import Platform


def test_parse_youtube_video_to_trend_item() -> None:
    video = parse_youtube_video(
        {
            "id": "abc123",
            "snippet": {
                "channelId": "channel_001",
                "channelTitle": "Creator",
                "title": "A useful short",
                "description": "desc",
                "publishedAt": "2026-05-16T01:02:03Z",
            },
            "statistics": {
                "viewCount": "1000",
                "likeCount": "120",
                "commentCount": "8",
            },
        }
    )

    trend = video.to_trend_item()

    assert trend.platform == Platform.YOUTUBE
    assert trend.source_id == "abc123"
    assert trend.author == "Creator"
    assert trend.view_count == 1000
    assert trend.published_at is not None
    assert trend.published_at.tzinfo == UTC


def test_calculate_outlier_score() -> None:
    assert calculate_outlier_score(video_views=5000, channel_median_views=1000) == 5.0
    assert calculate_outlier_score(video_views=5000, channel_median_views=0) == 5000.0


def test_quota_reserve() -> None:
    quota = YouTubeQuota(used=9_999, limit=10_000)

    assert quota.reserve(1).remaining == 0
    with pytest.raises(YouTubeQuotaExceededError):
        quota.reserve(2)


@pytest.mark.asyncio
async def test_videos_list_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YOUTUBE_API_KEY", "")
    adapter = YouTubeDataAdapter()

    with pytest.raises(YouTubeApiKeyMissingError):
        await adapter.videos_list(["abc123"])
