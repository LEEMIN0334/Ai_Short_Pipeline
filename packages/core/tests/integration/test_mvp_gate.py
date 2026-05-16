from datetime import UTC, datetime, timedelta

import pytest
from ai_shorts.agents.ass_generator import generate_ass_from_split
from ai_shorts.agents.benchmark import BenchmarkPolicy
from ai_shorts.agents.ffmpeg_composer import (
    build_ffmpeg_composition_plan,
    run_ffmpeg_composition,
)
from ai_shorts.agents.final_qc import evaluate_final_qc
from ai_shorts.agents.qc_retry import evaluate_qc_retry
from ai_shorts.agents.research_backend import ResearchBackendPolicy, build_research_package
from ai_shorts.agents.script_writer import write_script_from_benchmark
from ai_shorts.agents.splitter import split_script
from ai_shorts.agents.trend_scout import TrendScoutPolicy, run_trend_scout
from ai_shorts.schemas.composition_manifest import (
    CompositionManifest,
    CompositionSegment,
    MediaRef,
)
from ai_shorts.schemas.qc_report import QCRetryStatus
from ai_shorts.schemas.trend_item import Platform, TrendItem


def _trend(source_id: str, *, now: datetime) -> TrendItem:
    return TrendItem(
        source_id=source_id,
        platform=Platform.INSTAGRAM,
        url=f"https://example.com/reel/{source_id}",
        title="Three-second pasta reveal",
        view_count=90_000,
        like_count=9_000,
        comment_count=850,
        share_count=500,
        published_at=now - timedelta(hours=2),
        collected_at=now,
        raw={
            "category": "food",
            "duration_ms": 32_000,
            "hook": "This pasta reveal takes three seconds",
            "copy_button_text": "Copy the reveal structure",
        },
    )


@pytest.mark.asyncio
async def test_mvp_gate_runs_collection_to_final_qc_without_external_services() -> None:
    now = datetime(2026, 5, 16, 12, tzinfo=UTC)

    async def instagram_source() -> list[TrendItem]:
        return [_trend("ig_mvp", now=now)]

    trend_run = await run_trend_scout(
        {"instagram": instagram_source},
        policy=TrendScoutPolicy(min_views=100, source_timeout_seconds=None),
        now=now,
    )
    research_package = build_research_package(
        trend_run,
        policy=ResearchBackendPolicy(
            benchmark_policy=BenchmarkPolicy(max_templates=1),
            min_templates_for_generation=1,
        ),
        now=now,
    )
    script = write_script_from_benchmark(
        research_package.benchmarks[0],
        research_report=research_package.report,
    )
    script_split = split_script(script)
    ass_document = generate_ass_from_split(script_split)
    manifest = CompositionManifest(
        script_id=script.id,
        output_ratio="9:16",
        fps=30,
        segments=[
            CompositionSegment(
                index=index,
                video=MediaRef(uri=f"assets/mvp-video-{index:02d}.mp4", mime_type="video/mp4"),
                voiceover=MediaRef(uri=f"assets/mvp-voice-{index:02d}.wav", mime_type="audio/wav"),
                subtitle_ass="build/composition/mvp.ass",
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
            )
            for index, segment in enumerate(script_split.segments)
        ],
    )
    plan = build_ffmpeg_composition_plan(
        manifest,
        output_uri="build/composition/mvp-final.mp4",
    )
    commands: list[list[str]] = []

    async def runner(command: list[str]) -> None:
        commands.append(command)

    render_result = await run_ffmpeg_composition(plan, runner=runner)
    final_qc = evaluate_final_qc(
        manifest,
        MediaRef(
            uri=render_result.output_uri,
            mime_type="video/mp4",
            duration_ms=plan.duration_ms,
        ),
        target_id="approval-mvp-001",
    )
    retry_decision = evaluate_qc_retry(final_qc, attempt_number=1)

    assert research_package.ready_for_generation is True
    assert script.target_duration_ms == 32_000
    assert ass_document.event_count == len(script_split.segments)
    assert plan.duration_ms == script.target_duration_ms
    assert render_result.commands_executed == len(manifest.segments) + 1
    assert commands[-1] == plan.final_command
    assert final_qc.passed is True
    assert retry_decision.status == QCRetryStatus.APPROVED
