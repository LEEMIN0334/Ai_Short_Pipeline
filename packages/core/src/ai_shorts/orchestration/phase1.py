import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, cast

from celery import chain
from celery.canvas import Signature
from pydantic import BaseModel, Field

from ai_shorts.agents.analyzer import analyze_trend_scout_run
from ai_shorts.agents.benchmark import BenchmarkPolicy
from ai_shorts.agents.research_backend import (
    ResearchBackendPolicy,
    ResearchPackage,
    build_research_package,
    render_research_handoff,
)
from ai_shorts.agents.trend_scout import (
    TrendFetch,
    TrendScoutPolicy,
    TrendScoutRun,
    run_trend_scout,
)
from ai_shorts.orchestration.celery_app import celery_app
from ai_shorts.schemas.trend_item import TrendItem

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
    """Collect trend candidates and run deterministic curation when fixtures are provided."""

    if _has_trend_fixture_payload(payload):
        run = asyncio.run(_collect_fixture_trends(payload))
        return {
            **payload,
            "stage": "collected",
            "collected_source_names": [source.source for source in run.sources],
            "trend_scout_run": run.model_dump(mode="json"),
        }

    return {
        **payload,
        "stage": "collected",
        "collected_source_names": payload.get("source_names", []),
    }


@celery_app.task(name=PHASE1_TASK_ANALYZE)  # type: ignore[untyped-decorator]
def analyze_research_task(payload: dict[str, Any]) -> dict[str, Any]:
    """Analyze a collected Trend Scout run when one is present."""

    run = _trend_scout_run_from_payload(payload)
    if run is not None:
        report = analyze_trend_scout_run(run, now=_requested_at(payload))
        return {
            **payload,
            "stage": "analyzed",
            "research_report": report.model_dump(mode="json"),
        }

    return {**payload, "stage": "analyzed"}


@celery_app.task(name=PHASE1_TASK_BENCHMARK)  # type: ignore[untyped-decorator]
def build_benchmarks_task(payload: dict[str, Any]) -> dict[str, Any]:
    """Build a research package with benchmark templates when trend data is present."""

    max_templates = payload.get("max_templates", 0)
    run = _trend_scout_run_from_payload(payload)
    if run is not None:
        package = _build_research_package(payload, run)
        return {
            **payload,
            "stage": "benchmarked",
            "benchmark_slots": len(package.benchmarks),
            "research_package": package.model_dump(mode="json"),
        }

    return {
        **payload,
        "stage": "benchmarked",
        "benchmark_slots": max_templates if isinstance(max_templates, int) else 0,
    }


@celery_app.task(name=PHASE1_TASK_HANDOFF)  # type: ignore[untyped-decorator]
def render_handoff_task(payload: dict[str, Any]) -> dict[str, Any]:
    """Render a Person A handoff when a research package is available."""

    package = _research_package_from_payload(payload)
    if package is not None:
        return {
            **payload,
            "stage": "handoff_ready",
            "ready_for_generation": package.ready_for_generation,
            "warnings": package.warnings,
            "research_handoff_markdown": render_research_handoff(package),
        }

    return {**payload, "stage": "handoff_ready"}


def _has_trend_fixture_payload(payload: Mapping[str, Any]) -> bool:
    return isinstance(payload.get("trend_items_by_source"), dict)


async def _collect_fixture_trends(payload: Mapping[str, Any]) -> TrendScoutRun:
    return await run_trend_scout(
        _trend_sources_from_payload(payload),
        policy=_trend_scout_policy(payload),
        now=_requested_at(payload),
        concurrent=False,
    )


def _trend_sources_from_payload(payload: Mapping[str, Any]) -> dict[str, TrendFetch]:
    raw_sources = payload.get("trend_items_by_source")
    if not isinstance(raw_sources, dict):
        msg = "trend_items_by_source must be an object"
        raise ValueError(msg)

    sources: dict[str, TrendFetch] = {}
    for source_name, raw_items in raw_sources.items():
        if not isinstance(source_name, str):
            msg = "trend source names must be strings"
            raise ValueError(msg)
        if not isinstance(raw_items, list):
            msg = f"trend source {source_name} must contain a list of items"
            raise ValueError(msg)

        sources[source_name] = _make_static_fetch(
            [TrendItem.model_validate(raw_item) for raw_item in raw_items]
        )
    return sources


def _make_static_fetch(items: list[TrendItem]) -> TrendFetch:
    async def fetch() -> list[TrendItem]:
        return items

    return fetch


def _trend_scout_policy(payload: Mapping[str, Any]) -> TrendScoutPolicy:
    raw_policy = payload.get("trend_scout_policy")
    if isinstance(raw_policy, dict):
        return TrendScoutPolicy.model_validate(raw_policy)
    return TrendScoutPolicy()


def _trend_scout_run_from_payload(payload: Mapping[str, Any]) -> TrendScoutRun | None:
    raw_run = payload.get("trend_scout_run")
    if raw_run is None:
        return None
    return TrendScoutRun.model_validate(raw_run)


def _build_research_package(payload: Mapping[str, Any], run: TrendScoutRun) -> ResearchPackage:
    return build_research_package(
        run,
        policy=ResearchBackendPolicy(
            benchmark_policy=BenchmarkPolicy(max_templates=_max_templates(payload)),
            min_templates_for_generation=1,
        ),
        now=_requested_at(payload),
    )


def _research_package_from_payload(payload: Mapping[str, Any]) -> ResearchPackage | None:
    raw_package = payload.get("research_package")
    if raw_package is None:
        return None
    return ResearchPackage.model_validate(raw_package)


def _max_templates(payload: Mapping[str, Any]) -> int:
    raw_max_templates = payload.get("max_templates")
    if type(raw_max_templates) is int and raw_max_templates >= 1:
        return raw_max_templates
    return 3


def _requested_at(payload: Mapping[str, Any]) -> datetime:
    raw_requested_at = payload.get("requested_at")
    if isinstance(raw_requested_at, datetime):
        return _as_aware_utc(raw_requested_at)
    if isinstance(raw_requested_at, str):
        return _as_aware_utc(datetime.fromisoformat(raw_requested_at.replace("Z", "+00:00")))
    return datetime.now(UTC)


def _as_aware_utc(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)
