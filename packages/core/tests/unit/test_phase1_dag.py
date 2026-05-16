from datetime import UTC, datetime

from ai_shorts.config import Settings
from ai_shorts.orchestration.celery_app import create_celery_app
from ai_shorts.orchestration.phase1 import (
    PHASE1_TASK_ANALYZE,
    PHASE1_TASK_BENCHMARK,
    PHASE1_TASK_COLLECT,
    PHASE1_TASK_HANDOFF,
    Phase1DagRequest,
    analyze_research_task,
    build_benchmarks_task,
    build_phase1_dag,
    collect_trends_task,
    compile_phase1_dag_plan,
    render_handoff_task,
)
from ai_shorts.schemas.trend_item import Platform, TrendItem


def test_create_celery_app_uses_redis_url_for_broker_and_backend() -> None:
    settings = Settings(REDIS_URL="redis://localhost:6379/7")

    app = create_celery_app(settings)

    assert app.conf.broker_url == "redis://localhost:6379/7"
    assert app.conf.result_backend == "redis://localhost:6379/7"
    assert app.conf.task_default_queue == "ai_shorts"
    assert app.conf.task_serializer == "json"


def test_compile_phase1_dag_plan_is_serializable_and_ordered() -> None:
    request = Phase1DagRequest(
        job_id="phase1_001",
        source_names=["instagram", "youtube"],
        requested_at=datetime(2026, 5, 16, 10, 30, tzinfo=UTC),
    )

    plan = compile_phase1_dag_plan(request)

    assert plan.job_id == "phase1_001"
    assert plan.task_names == [
        PHASE1_TASK_COLLECT,
        PHASE1_TASK_ANALYZE,
        PHASE1_TASK_BENCHMARK,
        PHASE1_TASK_HANDOFF,
    ]
    assert plan.payload == {
        "job_id": "phase1_001",
        "source_names": ["instagram", "youtube"],
        "max_templates": 3,
        "requested_at": "2026-05-16T10:30:00Z",
    }


def test_build_phase1_dag_returns_celery_chain_with_expected_tasks() -> None:
    request = Phase1DagRequest(
        job_id="phase1_002",
        source_names=["reddit"],
        max_templates=2,
        requested_at=datetime(2026, 5, 16, tzinfo=UTC),
    )

    dag = build_phase1_dag(request)

    assert [task.name for task in dag.tasks] == [
        PHASE1_TASK_COLLECT,
        PHASE1_TASK_ANALYZE,
        PHASE1_TASK_BENCHMARK,
        PHASE1_TASK_HANDOFF,
    ]
    assert dag.tasks[0].args == (
        {
            "job_id": "phase1_002",
            "source_names": ["reddit"],
            "max_templates": 2,
            "requested_at": "2026-05-16T00:00:00Z",
        },
    )


def test_phase1_placeholder_tasks_advance_payload_stage() -> None:
    payload = {
        "job_id": "phase1_003",
        "source_names": ["instagram"],
        "max_templates": 2,
    }

    collected = collect_trends_task.run(payload)
    analyzed = analyze_research_task.run(collected)
    benchmarked = build_benchmarks_task.run(analyzed)
    handoff = render_handoff_task.run(benchmarked)

    assert collected["stage"] == "collected"
    assert collected["collected_source_names"] == ["instagram"]
    assert analyzed["stage"] == "analyzed"
    assert benchmarked["stage"] == "benchmarked"
    assert benchmarked["benchmark_slots"] == 2
    assert handoff["stage"] == "handoff_ready"


def test_phase1_tasks_run_fixture_trend_pipeline() -> None:
    trend = TrendItem(
        source_id="ig_phase1_fixture",
        platform=Platform.INSTAGRAM,
        url="https://example.com/reel/ig_phase1_fixture",
        title="Three-second pasta reveal",
        view_count=80_000,
        like_count=8_000,
        comment_count=900,
        share_count=400,
        published_at=datetime(2026, 5, 16, 8, tzinfo=UTC),
        collected_at=datetime(2026, 5, 16, 10, tzinfo=UTC),
        raw={
            "category": "food",
            "duration_ms": 32_000,
            "copy_button_text": "Copy the reveal structure",
        },
    )
    payload = {
        "job_id": "phase1_fixture",
        "source_names": ["instagram"],
        "max_templates": 1,
        "requested_at": "2026-05-16T10:00:00Z",
        "trend_scout_policy": {
            "min_views": 100,
            "max_items": 2,
            "source_timeout_seconds": None,
        },
        "trend_items_by_source": {
            "instagram": [trend.model_dump(mode="json")],
        },
    }

    collected = collect_trends_task.run(payload)
    analyzed = analyze_research_task.run(collected)
    benchmarked = build_benchmarks_task.run(analyzed)
    handoff = render_handoff_task.run(benchmarked)

    assert collected["stage"] == "collected"
    assert collected["collected_source_names"] == ["instagram"]
    assert collected["trend_scout_run"]["result"]["selected"][0]["trend"]["source_id"] == (
        "ig_phase1_fixture"
    )
    assert analyzed["stage"] == "analyzed"
    assert analyzed["research_report"]["title"] == (
        "Food Trend Brief: Three-second pasta reveal"
    )
    assert benchmarked["stage"] == "benchmarked"
    assert benchmarked["benchmark_slots"] == 1
    assert benchmarked["research_package"]["ready_for_generation"] is True
    assert handoff["stage"] == "handoff_ready"
    assert handoff["ready_for_generation"] is True
    assert "# Research Handoff" in handoff["research_handoff_markdown"]
    assert "Three-second pasta reveal" in handoff["research_handoff_markdown"]
