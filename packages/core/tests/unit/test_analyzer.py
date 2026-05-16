from datetime import UTC, datetime

from ai_shorts.agents.analyzer import AnalyzerPolicy, analyze_trend_scout_run
from ai_shorts.agents.trend_scout import (
    RejectedTrendItem,
    TrendScoutResult,
    TrendScoutRun,
    TrendSourceReport,
)
from ai_shorts.schemas.trend_item import Platform, ScoredTrendItem, TrendItem


def _trend(
    source_id: str,
    *,
    platform: Platform = Platform.INSTAGRAM,
    title: str = "",
    views: int = 1000,
    raw: dict[str, object] | None = None,
) -> TrendItem:
    return TrendItem(
        source_id=source_id,
        platform=platform,
        url=f"https://example.com/{source_id}",
        title=title,
        view_count=views,
        collected_at=datetime(2026, 5, 16, tzinfo=UTC),
        raw=raw or {},
    )


def _scored(
    source_id: str,
    *,
    score: float,
    category: str = "comedy",
    platform: Platform = Platform.INSTAGRAM,
    title: str = "",
    views: int = 1000,
) -> ScoredTrendItem:
    return ScoredTrendItem(
        trend=_trend(
            source_id,
            platform=platform,
            title=title,
            views=views,
            raw={"category": category},
        ),
        viral_score=score,
        category=category,
        reasons=["reach=1000", f"platform={platform.value}"],
    )


def test_analyze_trend_scout_run_builds_research_report() -> None:
    now = datetime(2026, 5, 16, 12, 30, tzinfo=UTC)
    run = TrendScoutRun(
        result=TrendScoutResult(
            selected=[
                _scored("top", score=42.3, title="Fast hook", views=4000),
                _scored(
                    "yt_1",
                    score=31.1,
                    category="education",
                    platform=Platform.YOUTUBE,
                    views=2500,
                ),
            ],
            rejected=[
                RejectedTrendItem(
                    trend=_trend("old", views=10),
                    reason="below_min_views",
                )
            ],
        ),
        sources=[
            TrendSourceReport(source="instagram", items_collected=2),
            TrendSourceReport(source="youtube", items_collected=1),
        ],
    )

    report = analyze_trend_scout_run(run, now=now)

    assert report.id == "trend-research-20260516123000"
    assert report.title == "Comedy Trend Brief: Fast hook"
    assert "2 curated trend(s) found" in report.summary
    assert "ready for benchmark review" in report.summary
    assert "## Ranked Trends" in report.body_markdown
    assert "Fast hook (instagram) - score 42.3" in report.body_markdown
    assert "- Sources checked: 2" in report.body_markdown
    assert report.sources[0].title == "Fast hook"
    assert report.sources[0].summary == (
        "instagram candidate scored 42.3 in category comedy."
    )


def test_analyze_trend_scout_run_reports_empty_or_failed_collection() -> None:
    now = datetime(2026, 5, 16, 12, 30, tzinfo=UTC)
    run = TrendScoutRun(
        result=TrendScoutResult(selected=[]),
        sources=[
            TrendSourceReport(
                source="reddit",
                items_collected=0,
                error="RuntimeError: rate limit",
            )
        ],
    )

    report = analyze_trend_scout_run(run, now=now)

    assert report.title == "No Trend Candidates Ready"
    assert "at least one source failed" in report.summary
    assert "- No ranked trends available." in report.body_markdown
    assert "- reddit: failed with RuntimeError: rate limit" in report.body_markdown
    assert report.sources == []


def test_analyzer_policy_limits_sources_and_ranked_items() -> None:
    run = TrendScoutRun(
        result=TrendScoutResult(
            selected=[
                _scored("first", score=20),
                _scored("second", score=19),
                _scored("third", score=18),
            ]
        ),
        sources=[],
    )
    policy = AnalyzerPolicy(max_report_sources=1, max_ranked_items=2)

    report = analyze_trend_scout_run(
        run,
        policy=policy,
        now=datetime(2026, 5, 16, tzinfo=UTC),
    )

    assert len(report.sources) == 1
    assert "1. first" in report.body_markdown
    assert "2. second" in report.body_markdown
    assert "3. third" not in report.body_markdown
