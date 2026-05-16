from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import ClassVar

import httpx
from pydantic import BaseModel, Field, HttpUrl

from ai_shorts.adapters.base import AdapterBase, CostSink
from ai_shorts.config import get_settings
from ai_shorts.schemas.trend_item import Platform, TrendItem


class YouTubeOperation(StrEnum):
    CHANNELS_LIST = "channels.list"
    VIDEOS_LIST = "videos.list"


class YouTubeVideo(BaseModel):
    video_id: str
    channel_id: str
    channel_title: str = ""
    title: str = ""
    description: str = ""
    published_at: datetime | None = None
    view_count: int = Field(default=0, ge=0)
    like_count: int = Field(default=0, ge=0)
    comment_count: int = Field(default=0, ge=0)
    raw: dict[str, object] = Field(default_factory=dict)

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"

    def to_trend_item(self, collected_at: datetime | None = None) -> TrendItem:
        return TrendItem(
            source_id=self.video_id,
            platform=Platform.YOUTUBE,
            url=HttpUrl(self.url),
            title=self.title,
            author=self.channel_title,
            view_count=self.view_count,
            like_count=self.like_count,
            comment_count=self.comment_count,
            share_count=None,
            published_at=self.published_at,
            collected_at=collected_at or datetime.now(UTC),
            raw={"channel_id": self.channel_id, **self.raw},
        )


class YouTubeQuota(BaseModel):
    used: int = Field(default=0, ge=0)
    limit: int = Field(default=10_000, gt=0)

    @property
    def remaining(self) -> int:
        return max(self.limit - self.used, 0)

    def reserve(self, cost: int) -> "YouTubeQuota":
        if cost > self.remaining:
            msg = f"YouTube quota exceeded: need {cost}, remaining {self.remaining}"
            raise YouTubeQuotaExceededError(msg)
        return YouTubeQuota(used=self.used + cost, limit=self.limit)


class YouTubeAdapterError(RuntimeError):
    """Base YouTube adapter error."""


class YouTubeApiKeyMissingError(YouTubeAdapterError):
    """Raised when YOUTUBE_API_KEY is required but missing."""


class YouTubeQuotaExceededError(YouTubeAdapterError):
    """Raised when the daily quota model would be exceeded."""


def calculate_outlier_score(video_views: int, channel_median_views: int) -> float:
    if video_views < 0 or channel_median_views < 0:
        msg = "View counts must be non-negative"
        raise ValueError(msg)
    if channel_median_views == 0:
        return float(video_views)
    return round(video_views / channel_median_views, 6)


def parse_youtube_video(item: dict[str, object]) -> YouTubeVideo:
    snippet = _object_dict(item.get("snippet"))
    statistics = _object_dict(item.get("statistics"))
    video_id = str(item.get("id", ""))

    published_at_raw = snippet.get("publishedAt")
    published_at = None
    if isinstance(published_at_raw, str):
        published_at = datetime.fromisoformat(published_at_raw.replace("Z", "+00:00"))

    return YouTubeVideo(
        video_id=video_id,
        channel_id=str(snippet.get("channelId", "")),
        channel_title=str(snippet.get("channelTitle", "")),
        title=str(snippet.get("title", "")),
        description=str(snippet.get("description", "")),
        published_at=published_at,
        view_count=_int_stat(statistics, "viewCount"),
        like_count=_int_stat(statistics, "likeCount"),
        comment_count=_int_stat(statistics, "commentCount"),
        raw=item,
    )


def _object_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    return {}


def _int_stat(statistics: dict[str, object], key: str) -> int:
    value = statistics.get(key, 0)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


class YouTubeDataAdapter(AdapterBase):
    service_name = "youtube"
    base_url = "https://www.googleapis.com/youtube/v3"
    quota_costs: ClassVar[dict[YouTubeOperation, int]] = {
        YouTubeOperation.CHANNELS_LIST: 1,
        YouTubeOperation.VIDEOS_LIST: 1,
    }

    def __init__(
        self,
        cost_sink: CostSink | None = None,
        client: httpx.AsyncClient | None = None,
        quota: YouTubeQuota | None = None,
    ) -> None:
        super().__init__(cost_sink=cost_sink)
        self._client = client
        self.quota = quota or YouTubeQuota()

    async def videos_list(self, video_ids: list[str]) -> list[YouTubeVideo]:
        api_key = get_settings().youtube_api_key
        if not api_key:
            msg = "YOUTUBE_API_KEY is required for videos.list"
            raise YouTubeApiKeyMissingError(msg)

        self.quota = self.quota.reserve(self.quota_costs[YouTubeOperation.VIDEOS_LIST])
        await self.record_cost(
            operation=YouTubeOperation.VIDEOS_LIST.value,
            usd=Decimal("0"),
            metadata={"quota_units": self.quota_costs[YouTubeOperation.VIDEOS_LIST]},
        )

        params = {
            "part": "snippet,statistics",
            "id": ",".join(video_ids),
            "key": api_key,
        }
        if self._client is not None:
            response = await self._client.get(f"{self.base_url}/videos", params=params)
            response.raise_for_status()
            payload = response.json()
        else:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(f"{self.base_url}/videos", params=params)
                response.raise_for_status()
                payload = response.json()

        items = payload.get("items", [])
        if not isinstance(items, list):
            return []
        return [parse_youtube_video(item) for item in items if isinstance(item, dict)]

    def estimate_cost(self, operation: str, units: int = 1) -> Decimal:
        _ = units
        if operation in {item.value for item in YouTubeOperation}:
            return Decimal("0")
        return Decimal("0")
