from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

import httpx
from pydantic import BaseModel, Field, HttpUrl

from ai_shorts.adapters.base import AdapterBase, CostSink
from ai_shorts.config import get_settings
from ai_shorts.schemas.trend_item import Platform, TrendItem


class RedditListing(StrEnum):
    HOT = "hot"
    TOP_WEEK = "top_week"
    TOP_MONTH = "top_month"


class RedditPost(BaseModel):
    post_id: str
    subreddit: str
    title: str
    author: str = ""
    permalink: str
    url: HttpUrl
    score: int = Field(default=0, ge=0)
    upvote_ratio: float | None = Field(default=None, ge=0, le=1)
    comment_count: int = Field(default=0, ge=0)
    created_at: datetime | None = None
    raw: dict[str, object] = Field(default_factory=dict)

    @property
    def reddit_url(self) -> str:
        return f"https://www.reddit.com{self.permalink}"

    def to_trend_item(self, collected_at: datetime | None = None) -> TrendItem:
        return TrendItem(
            source_id=self.post_id,
            platform=Platform.REDDIT,
            url=HttpUrl(self.reddit_url),
            title=self.title,
            author=self.author,
            view_count=None,
            like_count=self.score,
            comment_count=self.comment_count,
            share_count=None,
            published_at=self.created_at,
            collected_at=collected_at or datetime.now(UTC),
            raw={
                "subreddit": self.subreddit,
                "external_url": str(self.url),
                "upvote_ratio": self.upvote_ratio,
                **self.raw,
            },
        )


class RedditAdapterError(RuntimeError):
    """Base Reddit adapter error."""


def parse_reddit_post(child: dict[str, object]) -> RedditPost:
    data = _object_dict(child.get("data"))
    post_id = str(data.get("id", ""))
    permalink = str(data.get("permalink", f"/comments/{post_id}/"))
    url = str(data.get("url") or f"https://www.reddit.com{permalink}")
    created_utc = data.get("created_utc")
    created_at = None
    if isinstance(created_utc, int | float):
        created_at = datetime.fromtimestamp(created_utc, tz=UTC)

    return RedditPost(
        post_id=post_id,
        subreddit=str(data.get("subreddit", "")),
        title=str(data.get("title", "")),
        author=str(data.get("author", "")),
        permalink=permalink,
        url=HttpUrl(url),
        score=_safe_int(data.get("score")),
        upvote_ratio=_safe_float(data.get("upvote_ratio")),
        comment_count=_safe_int(data.get("num_comments")),
        created_at=created_at,
        raw=data,
    )


def parse_listing(payload: dict[str, object]) -> list[RedditPost]:
    data = _object_dict(payload.get("data"))
    children = data.get("children", [])
    if not isinstance(children, list):
        return []
    return [
        parse_reddit_post(child)
        for child in children
        if isinstance(child, dict) and isinstance(child.get("data"), dict)
    ]


def reddit_listing_path(subreddit: str, listing: RedditListing) -> str:
    clean_subreddit = subreddit.strip().strip("/")
    if not clean_subreddit:
        msg = "subreddit is required"
        raise ValueError(msg)
    if listing == RedditListing.TOP_WEEK:
        return f"/r/{clean_subreddit}/top.json?t=week"
    if listing == RedditListing.TOP_MONTH:
        return f"/r/{clean_subreddit}/top.json?t=month"
    return f"/r/{clean_subreddit}/hot.json"


def _object_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    return {}


def _safe_int(value: object) -> int:
    if isinstance(value, int):
        return max(value, 0)
    if isinstance(value, float):
        return max(int(value), 0)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


def _safe_float(value: object) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


class RedditApiAdapter(AdapterBase):
    service_name = "reddit"
    base_url = "https://www.reddit.com"

    def __init__(
        self,
        cost_sink: CostSink | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(cost_sink=cost_sink)
        self._client = client

    async def fetch_listing(
        self,
        subreddit: str,
        listing: RedditListing,
        limit: int = 25,
    ) -> list[RedditPost]:
        path = reddit_listing_path(subreddit=subreddit, listing=listing)
        params = {"limit": limit, "raw_json": 1}
        headers = {"User-Agent": get_settings().reddit_user_agent}

        await self.record_cost(
            operation=f"fetch_{listing.value}",
            usd=Decimal("0"),
            metadata={"subreddit": subreddit, "limit": limit},
        )

        if self._client is not None:
            response = await self._client.get(path, params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()
        else:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=30) as client:
                response = await client.get(path, params=params, headers=headers)
                response.raise_for_status()
                payload = response.json()

        if not isinstance(payload, dict):
            return []
        return parse_listing(payload)

    def estimate_cost(self, operation: str, units: int = 1) -> Decimal:
        _ = operation
        _ = units
        return Decimal("0")
