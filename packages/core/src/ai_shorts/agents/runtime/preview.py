from datetime import UTC, datetime, timedelta
from re import sub
from typing import cast

from pydantic import HttpUrl

from ai_shorts.agents.ass_generator import generate_ass_from_split
from ai_shorts.agents.benchmark import BenchmarkPolicy
from ai_shorts.agents.ffmpeg_composer import build_ffmpeg_composition_plan
from ai_shorts.agents.final_qc import evaluate_final_qc
from ai_shorts.agents.qc_retry import evaluate_qc_retry
from ai_shorts.agents.research_backend import (
    ResearchBackendPolicy,
    ResearchPackage,
    build_research_package,
)
from ai_shorts.agents.script_writer import write_script_from_benchmark
from ai_shorts.agents.splitter import split_script
from ai_shorts.agents.trend_scout import TrendScoutPolicy, run_trend_scout
from ai_shorts.schemas.composition_manifest import (
    CompositionManifest,
    CompositionSegment,
    MediaRef,
)
from ai_shorts.schemas.script import Script
from ai_shorts.schemas.trend_item import Platform, TrendItem


async def build_research_preview(topic: str) -> str:
    package = await _research_package(topic)
    lines = [
        f"Research preview: {_topic(topic)}",
        "Agents: Trend Scout -> Analyzer -> Benchmark -> Research Agent",
        f"Ready for generation: {'yes' if package.ready_for_generation else 'no'}",
        "",
        "Selected trend signals:",
    ]
    lines.extend(_report_bullets(package))
    lines.append("")
    lines.append("Benchmark templates:")
    lines.extend(
        f"- {benchmark.id}: {benchmark.title} ({benchmark.duration_ms // 1000}s)"
        for benchmark in package.benchmarks
    )
    if package.warnings:
        lines.append("")
        lines.append(f"Warnings: {', '.join(package.warnings)}")
    return "\n".join(lines)


async def build_script_preview(topic: str) -> str:
    package = await _research_package(topic)
    if not package.benchmarks:
        return f"Script Writer could not draft yet: no benchmarks for {_topic(topic)}"
    script = write_script_from_benchmark(
        package.benchmarks[0],
        research_report=package.report,
    )
    split = split_script(script)
    lines = [
        f"Script preview: {script.title}",
        "Agents: Research Agent -> Script Writer -> Splitter",
        f"Duration: {script.target_duration_ms // 1000}s",
        f"Scenes: {len(script.scenes)}",
        f"TTS/subtitle segments: {len(split.segments)}",
        "",
        "Draft lines:",
    ]
    lines.extend(_script_bullets(script))
    return "\n".join(lines)


async def build_mvp_preview(topic: str) -> str:
    package = await _research_package(topic)
    if not package.benchmarks:
        return f"MVP preview blocked: no benchmark templates for {_topic(topic)}"

    script = write_script_from_benchmark(
        package.benchmarks[0],
        research_report=package.report,
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
                video=MediaRef(
                    uri=f"manual://grok/{script.id}-clip-{index:02d}.mp4",
                    mime_type="video/mp4",
                ),
                voiceover=MediaRef(
                    uri=f"manual://typecast/{script.id}-voice-{index:02d}.wav",
                    mime_type="audio/wav",
                ),
                subtitle_ass=f"build/composition/{script.id}.ass",
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
            )
            for index, segment in enumerate(script_split.segments)
        ],
    )
    plan = build_ffmpeg_composition_plan(
        manifest,
        output_uri=f"build/composition/{script.id}-final.mp4",
    )
    final_qc = evaluate_final_qc(
        manifest,
        MediaRef(
            uri=plan.output_uri,
            mime_type="video/mp4",
            duration_ms=plan.duration_ms,
        ),
        target_id=f"approval-{script.id}",
    )
    retry = evaluate_qc_retry(final_qc, attempt_number=1)

    return "\n".join(
        [
            f"MVP preview: {_topic(topic)}",
            "Agents: Trend Scout -> Research -> Script -> Splitter -> ASS -> Composer -> QC",
            f"Research ready: {'yes' if package.ready_for_generation else 'no'}",
            f"Script: {script.id}",
            f"Subtitle events: {ass_document.event_count}",
            f"FFmpeg commands planned: {len(plan.segment_commands) + 1}",
            f"Output: {plan.output_uri}",
            f"Final QC: {'pass' if final_qc.passed else 'fail'} ({final_qc.overall_score})",
            f"Retry decision: {retry.status.value}",
            "",
            "No paid external API was called. This is a local agent gate preview.",
        ]
    )


def build_grok_prompt_preview(topic: str) -> str:
    clean_topic = _topic(topic)
    lines = [
        f"Grok loop plan: {clean_topic}",
        "Agent: Grok Clip Planner",
        "Use this as manual generation guidance for each 10-15s clip:",
    ]
    for index in range(1, 5):
        lines.append(
            f"- Clip {index:02d}: vertical 9:16 loop, stable camera, same first/last "
            f"frame, one clear subject, no text overlay, topic '{clean_topic}'."
        )
    lines.append("Dashboard project creation is available with: new <title>")
    return "\n".join(lines)


async def build_developer_preview(feature: str) -> str:
    package = await _research_package(feature)
    clean_feature = _topic(feature)
    top_template = package.benchmarks[0].id if package.benchmarks else "none"
    return "\n".join(
        [
            f"Developer plan: {clean_feature}",
            "Agents: Research Agent -> PM Supervisor -> Developer Agent",
            "Gate: Developer Agent waits for research direction and PM approval "
            "before code changes.",
            f"Research ready: {'yes' if package.ready_for_generation else 'no'}",
            f"Reference handoff: {package.report.id}",
            f"Primary benchmark/context: {top_template}",
            "",
            "Implementation approach:",
            "- Confirm the product requirement and user-facing behavior.",
            "- Identify the smallest repo surface that should change.",
            "- Make scoped code edits only after PM approval.",
            "- Add or update focused tests for the changed behavior.",
            "- Run ruff, mypy, and pytest before reporting done.",
            "",
            "Developer self-review gate:",
            "- Re-read every changed file and confirm the diff matches the approved plan.",
            "- Check for secret leakage, broad refactors, and unrelated file churn.",
            "- Verify user-facing behavior, error paths, and rollback impact.",
            "- Summarize residual risk and any test gaps before handoff.",
            "- If self-review fails, return the task to PM instead of claiming done.",
            "",
            "Current mode: planning only. No code was changed by this background worker.",
        ]
    )


async def _research_package(topic: str) -> ResearchPackage:
    now = datetime(2026, 5, 16, 12, tzinfo=UTC)

    async def instagram_source() -> list[TrendItem]:
        return [
            _trend(
                "ig_primary",
                topic=topic,
                platform=Platform.INSTAGRAM,
                title=f"{_topic(topic)} visual hook",
                views=90_000,
                likes=9_000,
                comments=850,
                shares=500,
                published_at=now - timedelta(hours=2),
                now=now,
            )
        ]

    async def youtube_source() -> list[TrendItem]:
        return [
            _trend(
                "yt_support",
                topic=topic,
                platform=Platform.YOUTUBE,
                title=f"{_topic(topic)} explainer angle",
                views=42_000,
                likes=2_800,
                comments=210,
                shares=80,
                published_at=now - timedelta(hours=6),
                now=now,
            )
        ]

    trend_run = await run_trend_scout(
        {"instagram": instagram_source, "youtube": youtube_source},
        policy=TrendScoutPolicy(
            max_items=2,
            min_views=100,
            source_timeout_seconds=None,
        ),
        now=now,
    )
    return build_research_package(
        trend_run,
        policy=ResearchBackendPolicy(
            benchmark_policy=BenchmarkPolicy(max_templates=2),
            min_templates_for_generation=1,
        ),
        now=now,
    )


def _trend(
    source_id: str,
    *,
    topic: str,
    platform: Platform,
    title: str,
    views: int,
    likes: int,
    comments: int,
    shares: int,
    published_at: datetime,
    now: datetime,
) -> TrendItem:
    return TrendItem(
        source_id=source_id,
        platform=platform,
        url=cast(HttpUrl, f"https://example.com/{platform.value}/{_slug(topic)}-{source_id}"),
        title=title,
        view_count=views,
        like_count=likes,
        comment_count=comments,
        share_count=shares,
        published_at=published_at,
        collected_at=now,
        raw={
            "category": _category(topic),
            "duration_ms": 32_000,
            "hook": f"Why {_topic(topic)} is moving right now",
            "copy_button_text": f"Use the {_topic(topic)} loop structure",
        },
    )


def _report_bullets(package: ResearchPackage) -> list[str]:
    return [f"- {source.title}: {source.summary}" for source in package.report.sources]


def _script_bullets(script: Script) -> list[str]:
    bullets: list[str] = []
    for scene in script.scenes:
        first_line = scene.lines[0] if scene.lines else None
        if first_line is not None:
            bullets.append(f"- Scene {scene.index + 1}: {first_line.text}")
    return bullets


def _topic(topic: str) -> str:
    clean = " ".join(topic.strip().split())
    return clean or "untitled short"


def _category(topic: str) -> str:
    clean = _topic(topic).lower()
    if any(token in clean for token in ["ai", "tech", "grok", "gemini"]):
        return "technology"
    if any(token in clean for token in ["money", "price", "startup"]):
        return "business"
    if any(token in clean for token in ["food", "recipe", "kitchen"]):
        return "food"
    return "culture"


def _slug(topic: str) -> str:
    slug = sub(r"[^a-zA-Z0-9]+", "-", topic.lower()).strip("-")
    return slug or "topic"
