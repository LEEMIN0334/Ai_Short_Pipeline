from datetime import UTC, datetime

from ai_shorts.agents.benchmark import BenchmarkPolicy
from ai_shorts.agents.research_backend import (
    ResearchBackendPolicy,
    build_research_package,
    render_research_handoff,
)
from ai_shorts.agents.trend_scout import (
    TrendScoutResult,
    TrendScoutRun,
    TrendSourceReport,
)
from ai_shorts.schemas.trend_item import Platform, ScoredTrendItem, TrendItem


def _scored(
    source_id: str,
    *,
    score: float = 45.0,
    title: str = "Loop hook",
    category: str = "comedy",
) -> ScoredTrendItem:
    return ScoredTrendItem(
        trend=TrendItem(
            source_id=source_id,
            platform=Platform.INSTAGRAM,
            url=f"https://example.com/reel/{source_id}",
            title=title,
            view_count=9000,
            like_count=700,
            comment_count=60,
            collected_at=datetime(2026, 5, 16, tzinfo=UTC),
            raw={"category": category, "duration_ms": 30000},
        ),
        viral_score=score,
        category=category,
        reasons=["reach=9000", "platform=instagram"],
    )


def test_build_research_package_combines_report_and_benchmarks() -> None:
    now = datetime(2026, 5, 16, 13, 5, tzinfo=UTC)
    run = TrendScoutRun(
        result=TrendScoutResult(
            selected=[
                _scored("ig_001", title="Loop hook"),
                _scored("ig_002", title="Second hook", score=38.0),
            ]
        ),
        sources=[TrendSourceReport(source="instagram", items_collected=2)],
    )

    package = build_research_package(run, now=now)

    assert package.ready_for_generation is True
    assert package.warnings == []
    assert package.report.id == "trend-research-20260516130500"
    assert "2 curated trend(s) found" in package.report.summary
    assert [benchmark.id for benchmark in package.benchmarks] == [
        "benchmark-01-instagram-ig-001",
        "benchmark-02-instagram-ig-002",
    ]


def test_build_research_package_can_block_on_source_failures() -> None:
    run = TrendScoutRun(
        result=TrendScoutResult(selected=[_scored("ig_001")]),
        sources=[
            TrendSourceReport(source="instagram", items_collected=1),
            TrendSourceReport(
                source="reddit",
                items_collected=0,
                error="RuntimeError: rate limit",
            ),
        ],
    )
    policy = ResearchBackendPolicy(fail_on_source_errors=True)

    package = build_research_package(
        run,
        policy=policy,
        now=datetime(2026, 5, 16, tzinfo=UTC),
    )

    assert package.ready_for_generation is False
    assert package.warnings == ["source_failed:reddit:RuntimeError: rate limit"]


def test_build_research_package_warns_when_no_templates_are_ready() -> None:
    run = TrendScoutRun(
        result=TrendScoutResult(selected=[]),
        sources=[TrendSourceReport(source="instagram", items_collected=0)],
    )
    policy = ResearchBackendPolicy(
        benchmark_policy=BenchmarkPolicy(max_templates=1),
        min_templates_for_generation=1,
    )

    package = build_research_package(
        run,
        policy=policy,
        now=datetime(2026, 5, 16, tzinfo=UTC),
    )

    assert package.ready_for_generation is False
    assert package.benchmarks == []
    assert package.warnings == [
        "no_selected_trends",
        "insufficient_benchmark_templates:0/1",
    ]


def test_render_research_handoff_includes_summary_benchmarks_and_warnings() -> None:
    run = TrendScoutRun(
        result=TrendScoutResult(selected=[_scored("ig_001")]),
        sources=[
            TrendSourceReport(
                source="reddit",
                items_collected=0,
                error="TimeoutError:",
            )
        ],
    )
    package = build_research_package(
        run,
        now=datetime(2026, 5, 16, tzinfo=UTC),
    )

    handoff = render_research_handoff(package)

    assert handoff.startswith("# Research Handoff")
    assert "## Summary" in handoff
    assert "- benchmark-01-instagram-ig-001: Loop hook Benchmark" in handoff
    assert "- source_failed:reddit:TimeoutError:" in handoff
    assert "## Report" in handoff
