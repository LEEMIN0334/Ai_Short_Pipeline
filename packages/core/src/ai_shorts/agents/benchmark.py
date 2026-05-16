from collections.abc import Sequence
from re import sub
from typing import Self

from pydantic import BaseModel, Field, model_validator

from ai_shorts.schemas.benchmark_template import BenchmarkScene, BenchmarkTemplate
from ai_shorts.schemas.trend_item import ScoredTrendItem


class BenchmarkPolicy(BaseModel):
    """Rules for turning ranked trend candidates into reusable short templates."""

    template_id_prefix: str = "benchmark"
    default_duration_ms: int = Field(default=45000, gt=0)
    min_duration_ms: int = Field(default=15000, gt=0)
    max_duration_ms: int = Field(default=90000, gt=0)
    scene_count: int = Field(default=4, ge=3, le=6)
    max_templates: int = Field(default=3, ge=1)

    @model_validator(mode="after")
    def validate_duration_bounds(self) -> Self:
        if self.min_duration_ms > self.max_duration_ms:
            msg = "min_duration_ms must be less than or equal to max_duration_ms"
            raise ValueError(msg)
        if not self.min_duration_ms <= self.default_duration_ms <= self.max_duration_ms:
            msg = "default_duration_ms must be within min/max duration bounds"
            raise ValueError(msg)
        return self


def build_benchmark_templates(
    candidates: Sequence[ScoredTrendItem],
    policy: BenchmarkPolicy | None = None,
) -> list[BenchmarkTemplate]:
    """Build benchmark templates for the top curated trend candidates."""

    active_policy = policy or BenchmarkPolicy()
    return [
        build_benchmark_template(candidate, rank=index, policy=active_policy)
        for index, candidate in enumerate(
            candidates[: active_policy.max_templates],
            start=1,
        )
    ]


def build_benchmark_template(
    candidate: ScoredTrendItem,
    *,
    rank: int = 1,
    policy: BenchmarkPolicy | None = None,
) -> BenchmarkTemplate:
    """Build one deterministic benchmark template from a scored trend."""

    active_policy = policy or BenchmarkPolicy()
    trend = candidate.trend
    duration_ms = _duration_ms(candidate, active_policy)
    label = trend.title or trend.source_id

    return BenchmarkTemplate(
        id=_template_id(candidate, rank, active_policy),
        source_url=trend.url,
        title=f"{label} Benchmark",
        category=candidate.category,
        duration_ms=duration_ms,
        scenes=_scenes(candidate, duration_ms, active_policy),
        copy_button_text=_copy_button_text(candidate),
        notes=_notes(candidate),
    )


def _template_id(
    candidate: ScoredTrendItem,
    rank: int,
    policy: BenchmarkPolicy,
) -> str:
    trend = candidate.trend
    source_label = _slug(trend.source_id or str(trend.url))
    return f"{policy.template_id_prefix}-{rank:02d}-{trend.platform.value}-{source_label}"


def _duration_ms(candidate: ScoredTrendItem, policy: BenchmarkPolicy) -> int:
    raw_duration = candidate.trend.raw.get("duration_ms")
    if isinstance(raw_duration, int) and raw_duration > 0:
        return min(max(raw_duration, policy.min_duration_ms), policy.max_duration_ms)
    return policy.default_duration_ms


def _scenes(
    candidate: ScoredTrendItem,
    duration_ms: int,
    policy: BenchmarkPolicy,
) -> list[BenchmarkScene]:
    spans = _scene_spans(duration_ms, policy.scene_count)
    scene_builders = [
        _hook_scene,
        _context_scene,
        _proof_scene,
        _payoff_scene,
        _variation_scene,
        _loop_scene,
    ]
    return [
        scene_builders[index](candidate, index, start_ms, end_ms)
        for index, (start_ms, end_ms) in enumerate(spans)
    ]


def _scene_spans(duration_ms: int, scene_count: int) -> list[tuple[int, int]]:
    effective_scene_count = min(scene_count, max(duration_ms, 1))
    base = duration_ms // effective_scene_count
    remainder = duration_ms % effective_scene_count
    spans: list[tuple[int, int]] = []
    start_ms = 0
    for index in range(effective_scene_count):
        width = base + (1 if index < remainder else 0)
        end_ms = start_ms + width
        spans.append((start_ms, end_ms))
        start_ms = end_ms
    return spans


def _hook_scene(
    candidate: ScoredTrendItem,
    index: int,
    start_ms: int,
    end_ms: int,
) -> BenchmarkScene:
    label = candidate.trend.title or candidate.trend.source_id
    return BenchmarkScene(
        index=index,
        start_ms=start_ms,
        end_ms=end_ms,
        visual_summary=f"Open with the clearest visual promise from {label}.",
        hook=_hook_text(candidate),
        camera_motion="fast push-in or jump cut",
        on_screen_text=_short_text(label),
    )


def _context_scene(
    candidate: ScoredTrendItem,
    index: int,
    start_ms: int,
    end_ms: int,
) -> BenchmarkScene:
    return BenchmarkScene(
        index=index,
        start_ms=start_ms,
        end_ms=end_ms,
        visual_summary=(
            f"Show the category context and why {candidate.category} matters now."
        ),
        camera_motion="cut between 2-3 proof visuals",
        on_screen_text=f"{candidate.category.title()} signal",
    )


def _proof_scene(
    candidate: ScoredTrendItem,
    index: int,
    start_ms: int,
    end_ms: int,
) -> BenchmarkScene:
    trend = candidate.trend
    return BenchmarkScene(
        index=index,
        start_ms=start_ms,
        end_ms=end_ms,
        visual_summary=(
            f"Use engagement proof: views {trend.view_count or 0}, "
            f"likes {trend.like_count or 0}, comments {trend.comment_count or 0}."
        ),
        camera_motion="tight cuts synced to proof points",
        on_screen_text=f"Score {candidate.viral_score:.1f}",
    )


def _payoff_scene(
    candidate: ScoredTrendItem,
    index: int,
    start_ms: int,
    end_ms: int,
) -> BenchmarkScene:
    return BenchmarkScene(
        index=index,
        start_ms=start_ms,
        end_ms=end_ms,
        visual_summary="Deliver the payoff or contrast that makes the format repeatable.",
        camera_motion="hold briefly, then snap to final frame",
        on_screen_text=_copy_button_text(candidate),
    )


def _variation_scene(
    candidate: ScoredTrendItem,
    index: int,
    start_ms: int,
    end_ms: int,
) -> BenchmarkScene:
    return BenchmarkScene(
        index=index,
        start_ms=start_ms,
        end_ms=end_ms,
        visual_summary=f"Show a second angle or remix for {candidate.category}.",
        camera_motion="side-by-side or quick before-after",
        on_screen_text="Make it repeatable",
    )


def _loop_scene(
    candidate: ScoredTrendItem,
    index: int,
    start_ms: int,
    end_ms: int,
) -> BenchmarkScene:
    return BenchmarkScene(
        index=index,
        start_ms=start_ms,
        end_ms=end_ms,
        visual_summary="End on a loopable frame that points back to the hook.",
        camera_motion="match cut back to opening frame",
        on_screen_text=_short_text(candidate.trend.title or candidate.trend.source_id),
    )


def _hook_text(candidate: ScoredTrendItem) -> str:
    raw_hook = candidate.trend.raw.get("hook")
    if isinstance(raw_hook, str) and raw_hook.strip():
        return raw_hook.strip()
    return f"Why this {candidate.category} trend is moving now"


def _copy_button_text(candidate: ScoredTrendItem) -> str:
    raw_text = candidate.trend.raw.get("copy_button_text")
    if isinstance(raw_text, str) and raw_text.strip():
        return raw_text.strip()
    return f"Use this {candidate.category} structure"


def _notes(candidate: ScoredTrendItem) -> str:
    reasons = ", ".join(candidate.reasons) if candidate.reasons else "no reasons logged"
    return (
        f"Source {candidate.trend.platform.value}:{candidate.trend.source_id}; "
        f"viral_score={candidate.viral_score:.1f}; reasons={reasons}"
    )


def _short_text(value: str, limit: int = 42) -> str:
    stripped = " ".join(value.split())
    if len(stripped) <= limit:
        return stripped
    return f"{stripped[: limit - 3].rstrip()}..."


def _slug(value: str) -> str:
    normalized = sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return normalized or "candidate"
