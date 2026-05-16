import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from math import log10
from typing import Any

from pydantic import BaseModel, Field

from ai_shorts.schemas.trend_item import Platform, ScoredTrendItem, TrendItem

TrendFetch = Callable[[], Awaitable[Sequence[TrendItem]]]


class TrendScoutPolicy(BaseModel):
    """Deterministic curation rules for Phase 1 trend scouting."""

    max_items: int = Field(default=20, ge=1)
    min_views: int = Field(default=0, ge=0)
    max_age_hours: int | None = Field(default=168, ge=1)
    source_timeout_seconds: float | None = Field(default=30.0, gt=0)
    platform_weights: dict[Platform, float] = Field(
        default_factory=lambda: {
            Platform.INSTAGRAM: 1.1,
            Platform.YOUTUBE: 1.0,
            Platform.REDDIT: 0.85,
            Platform.TIKTOK: 1.05,
        }
    )


class RejectedTrendItem(BaseModel):
    trend: TrendItem
    reason: str


class TrendScoutResult(BaseModel):
    selected: list[ScoredTrendItem]
    rejected: list[RejectedTrendItem] = Field(default_factory=list)


class TrendSourceReport(BaseModel):
    source: str
    items_collected: int = Field(ge=0)
    error: str | None = None


class TrendScoutRun(BaseModel):
    result: TrendScoutResult
    sources: list[TrendSourceReport]


@dataclass(frozen=True)
class _SourceCollection:
    source_report: TrendSourceReport
    items: list[TrendItem]


async def run_trend_scout(
    sources: Mapping[str, TrendFetch],
    policy: TrendScoutPolicy | None = None,
    now: datetime | None = None,
    concurrent: bool = True,
) -> TrendScoutRun:
    """Collect candidates from async sources, then apply deterministic curation."""

    active_policy = policy or TrendScoutPolicy()
    candidates: list[TrendItem] = []

    source_reports = (
        await _collect_sources_concurrently(sources, active_policy)
        if concurrent
        else [
            await _collect_source(source_name, fetch, active_policy)
            for source_name, fetch in sources.items()
        ]
    )
    for report in source_reports:
        candidates.extend(report.items)

    return TrendScoutRun(
        result=curate_trends(candidates, policy=active_policy, now=now),
        sources=[report.source_report for report in source_reports],
    )


async def _collect_sources_concurrently(
    sources: Mapping[str, TrendFetch],
    policy: TrendScoutPolicy,
) -> list["_SourceCollection"]:
    tasks = [
        _collect_source(source_name, fetch, policy)
        for source_name, fetch in sources.items()
    ]
    if not tasks:
        return []
    return list(await asyncio.gather(*tasks))


async def _collect_source(
    source_name: str,
    fetch: TrendFetch,
    policy: TrendScoutPolicy,
) -> "_SourceCollection":
    try:
        source_items = list(await _fetch_with_timeout(fetch, policy))
    except Exception as exc:
        return _SourceCollection(
            source_report=TrendSourceReport(
                source=source_name,
                items_collected=0,
                error=f"{type(exc).__name__}: {exc}",
            ),
            items=[],
        )

    return _SourceCollection(
        source_report=TrendSourceReport(
            source=source_name,
            items_collected=len(source_items),
        ),
        items=source_items,
    )


async def _fetch_with_timeout(
    fetch: TrendFetch,
    policy: TrendScoutPolicy,
) -> Sequence[TrendItem]:
    if policy.source_timeout_seconds is None:
        return await fetch()
    return await asyncio.wait_for(fetch(), timeout=policy.source_timeout_seconds)


def curate_trends(
    candidates: list[TrendItem],
    policy: TrendScoutPolicy | None = None,
    now: datetime | None = None,
) -> TrendScoutResult:
    """Deduplicate, filter, score, and rank raw trend candidates."""

    active_policy = policy or TrendScoutPolicy()
    reference_time = _as_aware_utc(now or datetime.now(UTC))
    rejected: list[RejectedTrendItem] = []
    best_by_key: dict[str, TrendItem] = {}

    for candidate in candidates:
        rejection_reason = _rejection_reason(candidate, active_policy, reference_time)
        if rejection_reason:
            rejected.append(RejectedTrendItem(trend=candidate, reason=rejection_reason))
            continue

        key = _dedupe_key(candidate)
        current = best_by_key.get(key)
        if current is None or _base_signal(candidate) > _base_signal(current):
            if current is not None:
                rejected.append(RejectedTrendItem(trend=current, reason="duplicate_lower_signal"))
            best_by_key[key] = candidate
        else:
            rejected.append(RejectedTrendItem(trend=candidate, reason="duplicate_lower_signal"))

    scored = [
        _score_trend(candidate, active_policy, reference_time)
        for candidate in best_by_key.values()
    ]
    scored.sort(key=lambda item: item.viral_score, reverse=True)

    return TrendScoutResult(
        selected=scored[: active_policy.max_items],
        rejected=rejected,
    )


def _score_trend(
    trend: TrendItem,
    policy: TrendScoutPolicy,
    now: datetime,
) -> ScoredTrendItem:
    views = trend.view_count or 0
    likes = trend.like_count or 0
    comments = trend.comment_count or 0
    shares = trend.share_count or 0

    reach_score = log10(views + 1) * 10
    engagement_score = log10(likes + comments * 2 + shares * 3 + 1) * 8
    recency_score = _recency_score(trend, now)
    platform_weight = policy.platform_weights.get(trend.platform, 1.0)
    viral_score = round((reach_score + engagement_score + recency_score) * platform_weight, 4)

    reasons = [
        f"reach={views}",
        f"engagement={likes + comments + shares}",
        f"platform={trend.platform.value}",
    ]
    if trend.published_at is not None:
        age_hours = _age_hours(trend.published_at, now)
        reasons.append(f"age_hours={age_hours:.1f}")

    return ScoredTrendItem(
        trend=trend,
        viral_score=viral_score,
        category=_category_for(trend),
        reasons=reasons,
    )


def _rejection_reason(
    trend: TrendItem,
    policy: TrendScoutPolicy,
    now: datetime,
) -> str | None:
    if trend.view_count is not None and trend.view_count < policy.min_views:
        return "below_min_views"

    if policy.max_age_hours is not None and trend.published_at is not None:
        if _age_hours(trend.published_at, now) > policy.max_age_hours:
            return "stale"

    return None


def _base_signal(trend: TrendItem) -> int:
    return (
        (trend.view_count or 0)
        + (trend.like_count or 0) * 2
        + (trend.comment_count or 0) * 3
        + (trend.share_count or 0) * 4
    )


def _recency_score(trend: TrendItem, now: datetime) -> float:
    if trend.published_at is None:
        return 0.0
    age_hours = max(_age_hours(trend.published_at, now), 0.0)
    return max(0.0, 12.0 - age_hours / 12.0)


def _age_hours(timestamp: datetime, now: datetime) -> float:
    return (_as_aware_utc(now) - _as_aware_utc(timestamp)).total_seconds() / 3600


def _as_aware_utc(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)


def _dedupe_key(trend: TrendItem) -> str:
    normalized_url = str(trend.url).split("?", 1)[0].rstrip("/")
    return f"{trend.platform.value}:{trend.source_id or normalized_url}"


def _category_for(trend: TrendItem) -> str:
    category = trend.raw.get("category")
    if isinstance(category, str) and category.strip():
        return category.strip().lower()
    tags = trend.raw.get("tags")
    if isinstance(tags, list):
        first_tag = _first_string(tags)
        if first_tag is not None:
            return first_tag.lower()
    return "uncategorized"


def _first_string(values: list[Any]) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None
