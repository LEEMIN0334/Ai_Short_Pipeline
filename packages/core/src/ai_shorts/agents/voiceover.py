import re
from collections.abc import Sequence

from pydantic import BaseModel, Field

from ai_shorts.adapters.typecast import TypecastAdapter
from ai_shorts.observability.cost_guard import (
    CostGuardDecision,
    CostGuardPolicy,
    estimate_adapter_operation,
    evaluate_cost_guard,
)
from ai_shorts.schemas.composition_manifest import MediaRef
from ai_shorts.schemas.script import ScriptSegment, ScriptSplit
from ai_shorts.storage.local import LocalStorage


class VoiceoverPolicy(BaseModel):
    """Rules for producing Typecast voiceover assets from script segments."""

    storage_prefix: str = "voiceovers"
    language: str = "kor"
    audio_format: str = "wav"
    prompt: dict[str, object] | None = None
    volume: int = Field(default=100, ge=0, le=200)
    audio_pitch: int = Field(default=0, ge=-24, le=24)
    audio_tempo: float = Field(default=1.0, gt=0)


class VoiceoverAsset(BaseModel):
    segment_id: str
    scene_index: int = Field(ge=0)
    line_index: int = Field(ge=0)
    chunk_index: int = Field(ge=0)
    text: str
    media: MediaRef


class VoiceoverBatchResult(BaseModel):
    script_id: str
    assets: list[VoiceoverAsset] = Field(default_factory=list)
    cost_guard: CostGuardDecision
    used_typecast: bool


async def synthesize_voiceovers(
    split: ScriptSplit,
    *,
    adapter: TypecastAdapter | None = None,
    storage: LocalStorage | None = None,
    policy: VoiceoverPolicy | None = None,
    cost_guard_policy: CostGuardPolicy | None = None,
    confirmation: str | None = None,
) -> VoiceoverBatchResult:
    """Synthesize every script segment with Typecast after a pre-flight cost check."""

    active_policy = policy or VoiceoverPolicy()
    active_adapter = adapter or TypecastAdapter()
    active_storage = storage or LocalStorage()
    units = _billable_units(split.segments)
    decision = evaluate_cost_guard(
        [
            estimate_adapter_operation(
                active_adapter,
                "text-to-speech",
                units=units,
                metadata={
                    "script_id": split.script_id,
                    "segment_count": len(split.segments),
                    "total_chars": sum(len(segment.text) for segment in split.segments),
                },
            )
        ],
        policy=cost_guard_policy,
        confirmation=confirmation,
    )
    if not decision.approved:
        return VoiceoverBatchResult(
            script_id=split.script_id,
            assets=[],
            cost_guard=decision,
            used_typecast=False,
        )

    assets: list[VoiceoverAsset] = []
    try:
        for segment in split.segments:
            result = await active_adapter.synthesize(
                segment.text,
                language=active_policy.language,
                prompt=active_policy.prompt,
                volume=active_policy.volume,
                audio_pitch=active_policy.audio_pitch,
                audio_tempo=active_policy.audio_tempo,
                audio_format=active_policy.audio_format,
                metadata={
                    "script_id": split.script_id,
                    "segment_id": segment.segment_id,
                    "scene_index": segment.scene_index,
                    "line_index": segment.line_index,
                    "chunk_index": segment.chunk_index,
                },
            )
            key = _storage_key(
                split.script_id,
                segment,
                extension=_extension(result.content_type, result.audio_format),
                policy=active_policy,
            )
            uri = await active_storage.put_bytes(key, result.audio_bytes)
            assets.append(
                VoiceoverAsset(
                    segment_id=segment.segment_id,
                    scene_index=segment.scene_index,
                    line_index=segment.line_index,
                    chunk_index=segment.chunk_index,
                    text=segment.text,
                    media=MediaRef(
                        uri=uri,
                        mime_type=result.content_type,
                        duration_ms=segment.end_ms - segment.start_ms,
                    ),
                )
            )
    finally:
        if adapter is None:
            await active_adapter.aclose()

    return VoiceoverBatchResult(
        script_id=split.script_id,
        assets=assets,
        cost_guard=decision,
        used_typecast=True,
    )


def _billable_units(segments: Sequence[ScriptSegment]) -> int:
    return sum(max(1, (len(segment.text) + 999) // 1000) for segment in segments)


def _storage_key(
    script_id: str,
    segment: ScriptSegment,
    *,
    extension: str,
    policy: VoiceoverPolicy,
) -> str:
    return (
        f"{_safe_path_part(policy.storage_prefix)}/"
        f"{_safe_path_part(script_id)}/"
        f"{_safe_path_part(segment.segment_id)}.{extension}"
    )


def _extension(content_type: str, audio_format: str) -> str:
    if "/" in content_type:
        subtype = content_type.split("/", 1)[1].split(";", 1)[0].strip()
        if subtype:
            return _safe_path_part(subtype)
    return _safe_path_part(audio_format)


def _safe_path_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-") or "asset"
