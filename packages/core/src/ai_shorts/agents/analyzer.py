from collections import Counter
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from ai_shorts.agents.trend_scout import TrendScoutRun, TrendSourceReport
from ai_shorts.schemas.research_report import ResearchReport, ResearchSource
from ai_shorts.schemas.trend_item import ScoredTrendItem


class AnalyzerPolicy(BaseModel):
    """Rules for converting curated trends into an editorial research report."""

    report_id_prefix: str = "trend-research"
    max_report_sources: int = Field(default=5, ge=1)
    max_ranked_items: int = Field(default=10, ge=1)
    min_recommendation_score: float = Field(default=35.0, ge=0)


def analyze_trend_scout_run(
    run: TrendScoutRun,
    policy: AnalyzerPolicy | None = None,
    now: datetime | None = None,
) -> ResearchReport:
    """Build a deterministic Phase 1 research report from Trend Scout output."""

    active_policy = policy or AnalyzerPolicy()
    created_at = _as_aware_utc(now or datetime.now(UTC))
    selected = run.result.selected[: active_policy.max_ranked_items]
    failed_sources = [source for source in run.sources if source.error is not None]

    return ResearchReport(
        id=_report_id(active_policy, created_at),
        title=_report_title(selected),
        summary=_summary(selected, failed_sources, active_policy),
        body_markdown=_body_markdown(selected, run, failed_sources, active_policy),
        sources=_research_sources(selected[: active_policy.max_report_sources]),
        created_at=created_at,
    )


def _report_id(policy: AnalyzerPolicy, created_at: datetime) -> str:
    return f"{policy.report_id_prefix}-{created_at:%Y%m%d%H%M%S}"


def _report_title(selected: list[ScoredTrendItem]) -> str:
    if not selected:
        return "No Trend Candidates Ready"
    top = selected[0]
    category = top.category.replace("_", " ").title()
    label = top.trend.title or top.trend.source_id
    return f"{category} Trend Brief: {label}"


def _summary(
    selected: list[ScoredTrendItem],
    failed_sources: list[TrendSourceReport],
    policy: AnalyzerPolicy,
) -> str:
    if not selected:
        if failed_sources:
            return "No trends passed curation; at least one source failed during collection."
        return "No trends passed curation in this run."

    top = selected[0]
    recommendation = (
        "ready for benchmark review"
        if top.viral_score >= policy.min_recommendation_score
        else "needs more validation"
    )
    source_note = (
        f" {len(failed_sources)} source(s) failed and should be retried."
        if failed_sources
        else ""
    )
    return (
        f"{len(selected)} curated trend(s) found. Top candidate "
        f"{top.trend.source_id} scored {top.viral_score:.1f} and is {recommendation}."
        f"{source_note}"
    )


def _body_markdown(
    selected: list[ScoredTrendItem],
    run: TrendScoutRun,
    failed_sources: list[TrendSourceReport],
    policy: AnalyzerPolicy,
) -> str:
    sections = [
        "## Overview",
        _overview(selected, run),
        "",
        "## Ranked Trends",
        _ranked_trends(selected),
        "",
        "## Source Health",
        _source_health(run),
        "",
        "## Recommendation",
        _recommendation(selected, failed_sources, policy),
    ]
    return "\n".join(sections)


def _overview(selected: list[ScoredTrendItem], run: TrendScoutRun) -> str:
    selected_count = len(selected)
    rejected_count = len(run.result.rejected)
    source_count = len(run.sources)
    category_counts = _category_counts(selected)
    platform_counts = _platform_counts(selected)
    return "\n".join(
        [
            f"- Selected trends: {selected_count}",
            f"- Rejected trends: {rejected_count}",
            f"- Sources checked: {source_count}",
            f"- Categories: {_format_counts(category_counts)}",
            f"- Platforms: {_format_counts(platform_counts)}",
        ]
    )


def _ranked_trends(selected: list[ScoredTrendItem]) -> str:
    if not selected:
        return "- No ranked trends available."

    lines: list[str] = []
    for index, item in enumerate(selected, start=1):
        trend = item.trend
        label = trend.title or trend.source_id
        lines.append(
            f"{index}. {label} ({trend.platform.value}) - "
            f"score {item.viral_score:.1f}, category {item.category}, "
            f"views {trend.view_count or 0}"
        )
    return "\n".join(lines)


def _source_health(run: TrendScoutRun) -> str:
    if not run.sources:
        return "- No sources were configured."

    lines: list[str] = []
    for source in run.sources:
        if source.error is None:
            lines.append(f"- {source.source}: collected {source.items_collected} item(s)")
        else:
            lines.append(f"- {source.source}: failed with {source.error}")
    return "\n".join(lines)


def _recommendation(
    selected: list[ScoredTrendItem],
    failed_sources: list[TrendSourceReport],
    policy: AnalyzerPolicy,
) -> str:
    if not selected:
        return "Retry failed sources or relax curation thresholds before scripting."

    top = selected[0]
    action = (
        "Move the top trend into benchmark review."
        if top.viral_score >= policy.min_recommendation_score
        else "Hold for more collection data before benchmark review."
    )
    if failed_sources:
        action += " Retry failed sources before finalizing the shortlist."
    return action


def _research_sources(selected: list[ScoredTrendItem]) -> list[ResearchSource]:
    return [
        ResearchSource(
            title=item.trend.title or item.trend.source_id,
            url=str(item.trend.url),
            summary=(
                f"{item.trend.platform.value} candidate scored "
                f"{item.viral_score:.1f} in category {item.category}."
            ),
        )
        for item in selected
    ]


def _category_counts(selected: list[ScoredTrendItem]) -> Counter[str]:
    return Counter(item.category for item in selected)


def _platform_counts(selected: list[ScoredTrendItem]) -> Counter[str]:
    return Counter(item.trend.platform.value for item in selected)


def _format_counts(counts: Counter[str]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{name}={count}" for name, count in sorted(counts.items()))


def _as_aware_utc(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)
