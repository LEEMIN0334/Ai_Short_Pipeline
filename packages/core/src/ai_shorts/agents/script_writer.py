from pydantic import BaseModel, Field

from ai_shorts.schemas.benchmark_template import BenchmarkScene, BenchmarkTemplate
from ai_shorts.schemas.research_report import ResearchReport
from ai_shorts.schemas.script import Script, ScriptLine, ScriptScene


class ScriptWriterPolicy(BaseModel):
    """Rules for deterministic draft script generation."""

    script_id_prefix: str = "script"
    narrator: str = "narrator"
    language: str = "ko"
    max_line_chars: int = Field(default=84, ge=20)


def write_script_from_benchmark(
    benchmark: BenchmarkTemplate,
    *,
    research_report: ResearchReport | None = None,
    policy: ScriptWriterPolicy | None = None,
) -> Script:
    """Create a first-pass script draft from a benchmark template."""

    active_policy = policy or ScriptWriterPolicy()
    return Script(
        id=f"{active_policy.script_id_prefix}-{benchmark.id}",
        template_id=benchmark.id,
        title=_script_title(benchmark),
        target_duration_ms=benchmark.duration_ms,
        scenes=[
            _script_scene(
                benchmark,
                scene,
                research_report=research_report,
                policy=active_policy,
            )
            for scene in benchmark.scenes
        ],
        language=active_policy.language,
    )


def write_scripts_for_package(
    benchmarks: list[BenchmarkTemplate],
    *,
    research_report: ResearchReport | None = None,
    policy: ScriptWriterPolicy | None = None,
) -> list[Script]:
    """Create script drafts for every benchmark in a research handoff."""

    return [
        write_script_from_benchmark(
            benchmark,
            research_report=research_report,
            policy=policy,
        )
        for benchmark in benchmarks
    ]


def _script_title(benchmark: BenchmarkTemplate) -> str:
    base_title = benchmark.title.removesuffix(" Benchmark").strip()
    return f"{base_title} Script"


def _script_scene(
    benchmark: BenchmarkTemplate,
    scene: BenchmarkScene,
    *,
    research_report: ResearchReport | None,
    policy: ScriptWriterPolicy,
) -> ScriptScene:
    return ScriptScene(
        index=scene.index,
        visual_prompt=_visual_prompt(benchmark, scene),
        lines=[
            ScriptLine(
                speaker=policy.narrator,
                text=_line_text(benchmark, scene, research_report, policy),
                start_ms=scene.start_ms,
                end_ms=scene.end_ms,
                emphasis_cue=_emphasis_cue(scene),
            )
        ],
    )


def _visual_prompt(benchmark: BenchmarkTemplate, scene: BenchmarkScene) -> str:
    parts = [scene.visual_summary]
    if scene.camera_motion:
        parts.append(f"Camera: {scene.camera_motion}.")
    if scene.on_screen_text:
        parts.append(f"On-screen text: {scene.on_screen_text}.")
    parts.append(f"Format reference: {benchmark.source_url}.")
    return " ".join(parts)


def _line_text(
    benchmark: BenchmarkTemplate,
    scene: BenchmarkScene,
    research_report: ResearchReport | None,
    policy: ScriptWriterPolicy,
) -> str:
    if scene.hook:
        text = scene.hook
    elif scene.index == 0:
        text = f"I'll show why this {benchmark.category} trend matters right now."
    elif scene.index == len(benchmark.scenes) - 1:
        text = f"This is the repeatable structure: {benchmark.copy_button_text}."
    else:
        text = _middle_scene_text(benchmark, scene, research_report)
    return _truncate(text, policy.max_line_chars)


def _middle_scene_text(
    benchmark: BenchmarkTemplate,
    scene: BenchmarkScene,
    research_report: ResearchReport | None,
) -> str:
    if research_report is not None and scene.index == 1:
        return research_report.summary
    if scene.on_screen_text:
        return f"Use {scene.on_screen_text} as the proof point, then move fast."
    return f"Build the repeatable signal for {benchmark.category} in one clear beat."


def _emphasis_cue(scene: BenchmarkScene) -> str | None:
    if scene.hook:
        return "hook"
    if scene.on_screen_text:
        return scene.on_screen_text
    return None


def _truncate(text: str, limit: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3].rstrip()}..."
