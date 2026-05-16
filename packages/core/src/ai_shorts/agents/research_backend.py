from datetime import UTC, datetime

from pydantic import BaseModel, Field

from ai_shorts.agents.analyzer import AnalyzerPolicy, analyze_trend_scout_run
from ai_shorts.agents.benchmark import BenchmarkPolicy, build_benchmark_templates
from ai_shorts.agents.trend_scout import TrendScoutRun, TrendSourceReport
from ai_shorts.schemas.benchmark_template import BenchmarkTemplate
from ai_shorts.schemas.research_report import ResearchReport


class ResearchBackendPolicy(BaseModel):
    """Phase 1 backend policy for research handoff package creation."""

    analyzer_policy: AnalyzerPolicy = Field(default_factory=AnalyzerPolicy)
    benchmark_policy: BenchmarkPolicy = Field(default_factory=BenchmarkPolicy)
    min_templates_for_generation: int = Field(default=1, ge=0)
    fail_on_source_errors: bool = False


class ResearchPackage(BaseModel):
    report: ResearchReport
    benchmarks: list[BenchmarkTemplate] = Field(default_factory=list)
    ready_for_generation: bool
    warnings: list[str] = Field(default_factory=list)


def build_research_package(
    run: TrendScoutRun,
    policy: ResearchBackendPolicy | None = None,
    now: datetime | None = None,
) -> ResearchPackage:
    """Build the Phase 1 handoff package from a completed Trend Scout run."""

    active_policy = policy or ResearchBackendPolicy()
    report = analyze_trend_scout_run(
        run,
        policy=active_policy.analyzer_policy,
        now=_as_aware_utc(now or datetime.now(UTC)),
    )
    benchmarks = build_benchmark_templates(
        run.result.selected,
        policy=active_policy.benchmark_policy,
    )
    failed_sources = [source for source in run.sources if source.error is not None]
    warnings = _warnings(run, benchmarks, failed_sources, active_policy)

    return ResearchPackage(
        report=report,
        benchmarks=benchmarks,
        ready_for_generation=_ready_for_generation(
            run,
            benchmarks,
            failed_sources,
            active_policy,
        ),
        warnings=warnings,
    )


def render_research_handoff(package: ResearchPackage) -> str:
    """Render a compact Markdown handoff for Person A review."""

    sections = [
        "# Research Handoff",
        "",
        "## Summary",
        package.report.summary,
        "",
        "## Benchmarks",
        _benchmark_lines(package.benchmarks),
        "",
        "## Warnings",
        _warning_lines(package.warnings),
        "",
        "## Report",
        package.report.body_markdown,
    ]
    return "\n".join(sections)


def _ready_for_generation(
    run: TrendScoutRun,
    benchmarks: list[BenchmarkTemplate],
    failed_sources: list[TrendSourceReport],
    policy: ResearchBackendPolicy,
) -> bool:
    if not run.result.selected:
        return False
    if len(benchmarks) < policy.min_templates_for_generation:
        return False
    if policy.fail_on_source_errors and failed_sources:
        return False
    return True


def _warnings(
    run: TrendScoutRun,
    benchmarks: list[BenchmarkTemplate],
    failed_sources: list[TrendSourceReport],
    policy: ResearchBackendPolicy,
) -> list[str]:
    warnings: list[str] = []
    if not run.result.selected:
        warnings.append("no_selected_trends")
    if len(benchmarks) < policy.min_templates_for_generation:
        warnings.append(
            "insufficient_benchmark_templates:"
            f"{len(benchmarks)}/{policy.min_templates_for_generation}"
        )
    warnings.extend(_source_failure_warnings(failed_sources))
    return warnings


def _source_failure_warnings(failed_sources: list[TrendSourceReport]) -> list[str]:
    return [
        f"source_failed:{source.source}:{source.error or 'unknown_error'}"
        for source in failed_sources
    ]


def _benchmark_lines(benchmarks: list[BenchmarkTemplate]) -> str:
    if not benchmarks:
        return "- No benchmark templates generated."
    return "\n".join(
        f"- {benchmark.id}: {benchmark.title} ({benchmark.duration_ms}ms)"
        for benchmark in benchmarks
    )


def _warning_lines(warnings: list[str]) -> str:
    if not warnings:
        return "- None"
    return "\n".join(f"- {warning}" for warning in warnings)


def _as_aware_utc(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)
