import json

from pydantic import BaseModel, Field

from ai_shorts.adapters.gemini import GeminiAdapter
from ai_shorts.observability.cost_guard import (
    CostGuardDecision,
    CostGuardPolicy,
    estimate_adapter_operation,
    evaluate_cost_guard,
)
from ai_shorts.schemas.benchmark_template import BenchmarkScene, BenchmarkTemplate
from ai_shorts.schemas.research_report import ResearchReport
from ai_shorts.schemas.script import Script, ScriptLine, ScriptScene


class ScriptWriterPolicy(BaseModel):
    """Rules for deterministic draft script generation."""

    script_id_prefix: str = "script"
    narrator: str = "narrator"
    language: str = "ko"
    max_line_chars: int = Field(default=84, ge=20)


class GeminiScriptDraftResult(BaseModel):
    """Script Writer result with explicit cost guard and fallback visibility."""

    script: Script
    used_gemini: bool
    cost_guard: CostGuardDecision
    raw_text: str = ""


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


async def write_script_with_gemini(
    benchmark: BenchmarkTemplate,
    *,
    research_report: ResearchReport | None = None,
    adapter: GeminiAdapter | None = None,
    policy: ScriptWriterPolicy | None = None,
    cost_guard_policy: CostGuardPolicy | None = None,
    confirmation: str | None = None,
) -> GeminiScriptDraftResult:
    """Draft a script with Gemini when Cost Guard approves, otherwise return fallback."""

    active_policy = policy or ScriptWriterPolicy()
    active_adapter = adapter or GeminiAdapter()
    estimate = estimate_adapter_operation(
        active_adapter,
        "generateContent",
        metadata={
            "template_id": benchmark.id,
            "agent": "script_writer",
        },
    )
    decision = evaluate_cost_guard(
        [estimate],
        policy=cost_guard_policy,
        confirmation=confirmation,
    )
    fallback = write_script_from_benchmark(
        benchmark,
        research_report=research_report,
        policy=active_policy,
    )
    if not decision.approved:
        return GeminiScriptDraftResult(
            script=fallback,
            used_gemini=False,
            cost_guard=decision,
            raw_text=decision.message,
        )

    result = await active_adapter.generate_text(
        _gemini_prompt(benchmark, research_report, active_policy),
        system_instruction=_gemini_system_instruction(),
        generation_config={
            "temperature": 0.7,
            "response_mime_type": "application/json",
        },
        metadata={
            "template_id": benchmark.id,
            "agent": "script_writer",
        },
    )
    return GeminiScriptDraftResult(
        script=_script_from_gemini_text(
            result.text,
            benchmark,
            fallback=fallback,
            policy=active_policy,
        ),
        used_gemini=True,
        cost_guard=decision,
        raw_text=result.text,
    )


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


def _gemini_system_instruction() -> str:
    return (
        "You write Korean short-form video scripts. Return only valid JSON. "
        "Do not include markdown fences or commentary."
    )


def _gemini_prompt(
    benchmark: BenchmarkTemplate,
    research_report: ResearchReport | None,
    policy: ScriptWriterPolicy,
) -> str:
    scene_lines = [
        {
            "index": scene.index,
            "start_ms": scene.start_ms,
            "end_ms": scene.end_ms,
            "visual_summary": scene.visual_summary,
            "hook": scene.hook or "",
            "on_screen_text": scene.on_screen_text or "",
        }
        for scene in benchmark.scenes
    ]
    payload = {
        "template": {
            "id": benchmark.id,
            "title": benchmark.title,
            "category": benchmark.category,
            "duration_ms": benchmark.duration_ms,
            "copy_button_text": benchmark.copy_button_text,
            "source_url": str(benchmark.source_url),
        },
        "research_summary": research_report.summary if research_report else "",
        "language": policy.language,
        "max_line_chars": policy.max_line_chars,
        "scenes": scene_lines,
        "required_json_shape": {
            "title": "short script title",
            "scenes": [
                {
                    "index": 0,
                    "line": "one spoken narrator line for the matching scene",
                    "emphasis_cue": "optional cue",
                }
            ],
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _script_from_gemini_text(
    text: str,
    benchmark: BenchmarkTemplate,
    *,
    fallback: Script,
    policy: ScriptWriterPolicy,
) -> Script:
    payload = _json_object(text)
    scene_payloads = payload.get("scenes")
    scene_lines = _scene_line_map(scene_payloads)
    title = payload.get("title")
    script_title = (
        str(title).strip()
        if isinstance(title, str) and title.strip()
        else fallback.title
    )

    return fallback.model_copy(
        update={
            "title": script_title,
            "scenes": [
                _gemini_script_scene(
                    benchmark,
                    scene,
                    fallback=fallback.scenes[index],
                    scene_lines=scene_lines,
                    policy=policy,
                )
                for index, scene in enumerate(benchmark.scenes)
            ],
        }
    )


def _gemini_script_scene(
    benchmark: BenchmarkTemplate,
    scene: BenchmarkScene,
    *,
    fallback: ScriptScene,
    scene_lines: dict[int, dict[str, str]],
    policy: ScriptWriterPolicy,
) -> ScriptScene:
    payload = scene_lines.get(scene.index, {})
    line_text = payload.get("line", "")
    if not line_text.strip():
        return fallback
    emphasis_cue = payload.get("emphasis_cue") or _emphasis_cue(scene)
    return ScriptScene(
        index=scene.index,
        visual_prompt=_visual_prompt(benchmark, scene),
        lines=[
            ScriptLine(
                speaker=policy.narrator,
                text=_truncate(line_text, policy.max_line_chars),
                start_ms=scene.start_ms,
                end_ms=scene.end_ms,
                emphasis_cue=emphasis_cue,
            )
        ],
    )


def _json_object(text: str) -> dict[str, object]:
    loaded = json.loads(text)
    if not isinstance(loaded, dict):
        msg = "Gemini script response must be a JSON object"
        raise RuntimeError(msg)
    return loaded


def _scene_line_map(value: object) -> dict[int, dict[str, str]]:
    if not isinstance(value, list):
        return {}
    mapped: dict[int, dict[str, str]] = {}
    for item in value:
        if not isinstance(item, dict):
            continue
        index = item.get("index")
        line = item.get("line")
        if not isinstance(index, int) or not isinstance(line, str):
            continue
        emphasis_cue = item.get("emphasis_cue")
        mapped[index] = {
            "line": line,
            "emphasis_cue": emphasis_cue if isinstance(emphasis_cue, str) else "",
        }
    return mapped
