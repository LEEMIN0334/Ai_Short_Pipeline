from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from ai_shorts.adapters._stub import StubAdapter
from ai_shorts.agents.benchmark import BenchmarkPolicy
from ai_shorts.agents.research_backend import (
    ResearchBackendPolicy,
    build_research_package,
    render_research_handoff,
)
from ai_shorts.agents.trend_scout import TrendScoutPolicy, run_trend_scout
from ai_shorts.observability.cost_guard import (
    CostGuardPolicy,
    CostGuardStatus,
    estimate_adapter_operation,
    evaluate_cost_guard,
)
from ai_shorts.orchestration.phase1 import (
    PHASE1_TASK_ANALYZE,
    PHASE1_TASK_BENCHMARK,
    PHASE1_TASK_COLLECT,
    PHASE1_TASK_HANDOFF,
    Phase1DagRequest,
    build_phase1_dag,
    compile_phase1_dag_plan,
)
from ai_shorts.schemas.trend_item import Platform, TrendItem


def _trend(
    source_id: str,
    *,
    platform: Platform,
    title: str,
    views: int,
    likes: int,
    comments: int,
    shares: int = 0,
    published_at: datetime,
    raw: dict[str, object] | None = None,
) -> TrendItem:
    return TrendItem(
        source_id=source_id,
        platform=platform,
        url=f"https://example.com/{platform.value}/{source_id}",
        title=title,
        view_count=views,
        like_count=likes,
        comment_count=comments,
        share_count=shares,
        published_at=published_at,
        collected_at=datetime(2026, 5, 16, 12, tzinfo=UTC),
        raw=raw or {},
    )


@pytest.mark.asyncio
async def test_phase1_collection_research_handoff_pipeline() -> None:
    now = datetime(2026, 5, 16, 12, tzinfo=UTC)

    async def instagram_source() -> list[TrendItem]:
        return [
            _trend(
                "ig_top",
                platform=Platform.INSTAGRAM,
                title="Three-second pasta reveal",
                views=80_000,
                likes=8_000,
                comments=900,
                shares=400,
                published_at=now - timedelta(hours=2),
                raw={
                    "category": "food",
                    "duration_ms": 32000,
                    "hook": "This pasta reveal takes three seconds",
                    "copy_button_text": "Copy the reveal structure",
                },
            ),
            _trend(
                "ig_too_small",
                platform=Platform.INSTAGRAM,
                title="Small sample",
                views=20,
                likes=1,
                comments=0,
                published_at=now - timedelta(hours=1),
            ),
        ]

    async def youtube_source() -> list[TrendItem]:
        return [
            _trend(
                "yt_support",
                platform=Platform.YOUTUBE,
                title="Kitchen timer remix",
                views=15_000,
                likes=1_000,
                comments=80,
                shares=20,
                published_at=now - timedelta(hours=5),
                raw={"category": "food", "duration_ms": 45000},
            )
        ]

    sources = {"instagram": instagram_source, "youtube": youtube_source}
    run = await run_trend_scout(
        sources,
        policy=TrendScoutPolicy(
            max_items=2,
            min_views=100,
            source_timeout_seconds=None,
        ),
        now=now,
    )
    cost_decision = evaluate_cost_guard(
        [estimate_adapter_operation(StubAdapter(), "do_thing", units=2)],
        policy=CostGuardPolicy(
            auto_approve_limit_usd=Decimal("0.01"),
            hard_limit_usd=Decimal("1.00"),
        ),
    )
    package = build_research_package(
        run,
        policy=ResearchBackendPolicy(
            benchmark_policy=BenchmarkPolicy(max_templates=2),
            min_templates_for_generation=1,
        ),
        now=now,
    )
    handoff = render_research_handoff(package)
    dag_request = Phase1DagRequest(
        job_id="phase1_integration",
        source_names=list(sources),
        max_templates=2,
        requested_at=now,
    )
    dag_plan = compile_phase1_dag_plan(dag_request)
    dag = build_phase1_dag(dag_request)

    assert [report.source for report in run.sources] == ["instagram", "youtube"]
    assert [item.trend.source_id for item in run.result.selected] == [
        "ig_top",
        "yt_support",
    ]
    assert [item.reason for item in run.result.rejected] == ["below_min_views"]
    assert cost_decision.status == CostGuardStatus.APPROVED
    assert cost_decision.approved is True
    assert package.ready_for_generation is True
    assert package.warnings == []
    assert package.report.title == "Food Trend Brief: Three-second pasta reveal"
    assert [benchmark.id for benchmark in package.benchmarks] == [
        "benchmark-01-instagram-ig-top",
        "benchmark-02-youtube-yt-support",
    ]
    assert package.benchmarks[0].copy_button_text == "Copy the reveal structure"
    assert "# Research Handoff" in handoff
    assert "Three-second pasta reveal" in handoff
    assert dag_plan.task_names == [
        PHASE1_TASK_COLLECT,
        PHASE1_TASK_ANALYZE,
        PHASE1_TASK_BENCHMARK,
        PHASE1_TASK_HANDOFF,
    ]
    assert [task.name for task in dag.tasks] == dag_plan.task_names
    assert dag_plan.payload["source_names"] == ["instagram", "youtube"]
