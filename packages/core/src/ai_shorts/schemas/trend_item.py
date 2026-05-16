from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl


class Platform(StrEnum):
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    REDDIT = "reddit"
    TIKTOK = "tiktok"


class TrendItem(BaseModel):
    source_id: str
    platform: Platform
    url: HttpUrl
    title: str = ""
    author: str = ""
    view_count: int | None = Field(default=None, ge=0)
    like_count: int | None = Field(default=None, ge=0)
    comment_count: int | None = Field(default=None, ge=0)
    share_count: int | None = Field(default=None, ge=0)
    published_at: datetime | None = None
    collected_at: datetime
    raw: dict[str, object] = Field(default_factory=dict)


class ScoredTrendItem(BaseModel):
    trend: TrendItem
    viral_score: float = Field(ge=0)
    category: str
    reasons: list[str] = Field(default_factory=list)
