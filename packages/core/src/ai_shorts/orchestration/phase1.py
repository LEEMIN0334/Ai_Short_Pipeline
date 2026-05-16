from datetime import UTC, datetime
from typing import Any, cast

from celery import chain
from celery.canvas import Signature
from pydantic import BaseModel, Field

from ai_shorts.orchestration.celery_app import celery_app

PHASE1_TASK_COLLECT = "ai_shorts.phase1.collect_trends"
PHASE1_TASK_ANALYZE = "ai_shorts.phase1.analyze_research"
PHASE1_TASK_BENCHMARK = "ai_shorts.phase1.build_benchmarks"
PHASE1_TASK_HANDOFF = "ai_shorts.phase1.render_handoff"


class Phase1DagRequest(BaseModel):
    job_id: str
    source_names: list[str] = Field(default_factory=list)
    max_templates: int = Field(default=3, ge=1)
    requested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Phase1DagPlan(BaseModel):
    job_id: str
    task_names: list[str]
    queue: str = "ai_shorts"
    payload: dict[str, Any]


def compile_phase1_dag_plan(request: Phase1DagRequest) -> Phase1DagPlan:
    """Compile a serializable Phase 1 DAG plan for inspection and dispatch."""

    task_names = [
        PHASE1_TASK_COLLECT,
        PHASE1_TASK_ANALYZE,
        PHASE1_TASK_BENCHMARK,
        PHASE1_TASK_HANDOFF,
    ]
    return Phase1DagPlan(
        job_id=request.job_id,
        task_names=task_names,
        payload=request.model_dump(mode="json"),
    )


def build_phase1_dag(request: Phase1DagRequest) -> Signature:
    """Build the basic Celery chain for Phase 1 collection and research."""

    payload = request.model_dump(mode="json")
    return cast(
        Signature,
        chain(
            collect_trends_task.s(payload),
            analyze_research_task.s(),
            build_benchmarks_task.s(),
            render_handoff_task.s(),
        ),
    )


@celery_app.task(name=PHASE1_TASK_COLLECT)  # type: ignore[untyped-decorator]
def collect_trends_task(payload: dict[str, Any]) -> dict[str, Any]:
    """Task placeholder for source collection adapters."""

    return {
        **payload,
        "stage": "collected",
        "collected_source_names": payload.get("source_names", []),
    }


@celery_app.task(name=PHASE1_TASK_ANALYZE)  # type: ignore[untyped-decorator]
def analyze_research_task(payload: dict[str, Any]) -> dict[str, Any]:
    """Task placeholder for Analyzer agent execution."""

    return {**payload, "stage": "analyzed"}


@celery_app.task(name=PHASE1_TASK_BENCHMARK)  # type: ignore[untyped-decorator]
def build_benchmarks_task(payload: dict[str, Any]) -> dict[str, Any]:
    """Task placeholder for Benchmark agent execution."""

    max_templates = payload.get("max_templates", 0)
    return {
        **payload,
        "stage": "benchmarked",
        "benchmark_slots": max_templates if isinstance(max_templates, int) else 0,
    }


@celery_app.task(name=PHASE1_TASK_HANDOFF)  # type: ignore[untyped-decorator]
def render_handoff_task(payload: dict[str, Any]) -> dict[str, Any]:
    """Task placeholder for final ResearchPackage handoff rendering."""

    return {**payload, "stage": "handoff_ready"}
