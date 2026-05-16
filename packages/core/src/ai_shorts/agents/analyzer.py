import json
import math
import re
from datetime import UTC, datetime
from decimal import Decimal

from ai_shorts.schemas.trend_item import ScoredTrendItem, TrendItem
from ai_shorts.storage.postgres import get_conn


class TrendAnalyzer:
    """Score and categorize collected trend items."""

    def score(self, trend: TrendItem, now: datetime | None = None) -> ScoredTrendItem:
        current_time = now or datetime.now(UTC)
        viral_score = calculate_viral_score(trend=trend, now=current_time)
        category = classify_category(trend)
        reasons = explain_score(trend=trend, viral_score=viral_score, category=category)
        return ScoredTrendItem(
            trend=trend,
            viral_score=viral_score,
            category=category,
            reasons=reasons,
        )

    async def score_and_store(self, trend_item_id: int) -> ScoredTrendItem:
        async with get_conn() as conn:
            row = await conn.fetchrow(
                """
                SELECT source_id, platform, url, title, author,
                       view_count, like_count, comment_count, share_count,
                       published_at, collected_at, raw
                FROM trend_item
                WHERE id = $1
                """,
                trend_item_id,
            )
            if row is None:
                msg = f"trend_item not found: {trend_item_id}"
                raise ValueError(msg)

            trend = TrendItem(
                source_id=row["source_id"],
                platform=row["platform"],
                url=row["url"],
                title=row["title"],
                author=row["author"],
                view_count=row["view_count"],
                like_count=row["like_count"],
                comment_count=row["comment_count"],
                share_count=row["share_count"],
                published_at=row["published_at"],
                collected_at=row["collected_at"],
                raw=_json_dict(row["raw"]),
            )
            scored = self.score(trend)
            await conn.execute(
                """
                INSERT INTO scored_trend_item (
                    trend_item_id, viral_score, category, reasons, scored_at
                )
                VALUES ($1, $2, $3, $4::jsonb, NOW())
                ON CONFLICT (trend_item_id)
                DO UPDATE SET
                    viral_score = EXCLUDED.viral_score,
                    category = EXCLUDED.category,
                    reasons = EXCLUDED.reasons,
                    scored_at = NOW()
                """,
                trend_item_id,
                Decimal(str(scored.viral_score)),
                scored.category,
                json.dumps(scored.reasons),
            )

        return scored


def calculate_viral_score(trend: TrendItem, now: datetime | None = None) -> float:
    current_time = now or datetime.now(UTC)
    views = trend.view_count or 0
    likes = trend.like_count or 0
    comments = trend.comment_count or 0
    shares = trend.share_count or 0

    engagement = likes + comments * 2.0 + shares * 3.0
    view_component = math.log10(views + 10)
    engagement_rate = engagement / max(views, 1)
    recency = _recency_multiplier(trend=trend, now=current_time)
    score = (view_component * 8.0 + engagement_rate * 100.0) * recency
    return round(max(score, 0.0), 6)


def classify_category(trend: TrendItem) -> str:
    text = f"{trend.title} {trend.raw}".lower()
    keyword_map = {
        "ai": ("ai", "chatgpt", "gpt", "agent", "automation", "prompt"),
        "business": ("startup", "business", "sales", "marketing", "money"),
        "education": ("tutorial", "how to", "learn", "guide", "explained"),
        "entertainment": ("funny", "meme", "story", "drama", "reaction"),
        "tech": ("code", "developer", "app", "software", "tool"),
    }
    for category, keywords in keyword_map.items():
        if any(_contains_keyword(text, keyword) for keyword in keywords):
            return category
    return "general"


def explain_score(trend: TrendItem, viral_score: float, category: str) -> list[str]:
    reasons = [f"category={category}", f"viral_score={viral_score:.3f}"]
    if trend.view_count is not None:
        reasons.append(f"views={trend.view_count}")
    if trend.like_count is not None:
        reasons.append(f"likes={trend.like_count}")
    if trend.comment_count is not None:
        reasons.append(f"comments={trend.comment_count}")
    if trend.share_count is not None:
        reasons.append(f"shares={trend.share_count}")
    return reasons


def _recency_multiplier(trend: TrendItem, now: datetime) -> float:
    timestamp = trend.published_at or trend.collected_at
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    age_hours = max((now - timestamp).total_seconds() / 3600, 0)
    return max(0.35, 1.0 / (1.0 + age_hours / 72.0))


def _contains_keyword(text: str, keyword: str) -> bool:
    if keyword.isalpha() and len(keyword) <= 3:
        return re.search(rf"\b{re.escape(keyword)}\b", text) is not None
    return keyword in text


def _json_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        loaded = json.loads(value)
        if isinstance(loaded, dict):
            return loaded
    return {}
