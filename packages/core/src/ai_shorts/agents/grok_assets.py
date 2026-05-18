import re
from collections.abc import Sequence

from pydantic import BaseModel, Field

from ai_shorts.schemas.composition_manifest import MediaRef
from ai_shorts.schemas.script import ScriptSegment, ScriptSplit


class GrokPromptPolicy(BaseModel):
    """Prompt defaults for manual Grok video generation."""

    output_ratio: str = "9:16"
    min_duration_seconds: int = Field(default=10, ge=1)
    max_duration_seconds: int = Field(default=15, ge=1)
    avoid_text_overlay: bool = True


class GrokClipPrompt(BaseModel):
    segment_id: str
    scene_index: int = Field(ge=0)
    clip_index: int = Field(ge=1)
    prompt: str
    first_frame_prompt: str
    last_frame_prompt: str
    expected_video_key: str


class GrokVideoAsset(BaseModel):
    segment_id: str
    scene_index: int = Field(ge=0)
    clip_index: int = Field(ge=1)
    media: MediaRef


def build_grok_clip_prompts(
    split: ScriptSplit,
    *,
    topic: str,
    policy: GrokPromptPolicy | None = None,
) -> list[GrokClipPrompt]:
    """Create one manual Grok generation prompt for each script segment."""

    active_policy = policy or GrokPromptPolicy()
    _validate_duration_range(active_policy)
    topic_text = " ".join(topic.split()) or split.script_id
    return [
        _prompt_for_segment(
            split,
            segment,
            clip_index=index,
            topic=topic_text,
            policy=active_policy,
        )
        for index, segment in enumerate(split.segments, start=1)
    ]


def register_grok_video_assets(
    split: ScriptSplit,
    video_uris: Sequence[str],
    *,
    mime_type: str = "video/mp4",
) -> list[GrokVideoAsset]:
    """Attach manually generated Grok video URIs to script segments."""

    uris = [uri.strip() for uri in video_uris]
    if len(uris) != len(split.segments):
        msg = f"Expected {len(split.segments)} video URI(s), got {len(uris)}"
        raise RuntimeError(msg)
    assets: list[GrokVideoAsset] = []
    for index, (segment, uri) in enumerate(zip(split.segments, uris, strict=True), start=1):
        if not uri:
            msg = f"Video URI is required for segment {segment.segment_id}"
            raise RuntimeError(msg)
        assets.append(
            GrokVideoAsset(
                segment_id=segment.segment_id,
                scene_index=segment.scene_index,
                clip_index=index,
                media=MediaRef(
                    uri=uri,
                    mime_type=mime_type,
                    duration_ms=segment.end_ms - segment.start_ms,
                ),
            )
        )
    return assets


def _prompt_for_segment(
    split: ScriptSplit,
    segment: ScriptSegment,
    *,
    clip_index: int,
    topic: str,
    policy: GrokPromptPolicy,
) -> GrokClipPrompt:
    visual_prompt = str(segment.metadata.get("scene_visual_prompt") or "").strip()
    no_text = "No text overlay." if policy.avoid_text_overlay else ""
    prompt = " ".join(
        part
        for part in [
            (
                f"Create a {policy.min_duration_seconds}-{policy.max_duration_seconds} second "
                f"vertical {policy.output_ratio} Grok video loop for '{topic}'."
            ),
            f"This is clip {clip_index} for script {split.script_id}.",
            f"Spoken line context: {segment.text}",
            f"Visual direction: {visual_prompt}" if visual_prompt else "",
            "Use one clear subject, stable camera, consistent lighting, and clean motion.",
            "Make the first and last frame visually compatible for seamless looping.",
            no_text,
        ]
        if part
    )
    return GrokClipPrompt(
        segment_id=segment.segment_id,
        scene_index=segment.scene_index,
        clip_index=clip_index,
        prompt=prompt,
        first_frame_prompt="Start with the clearest readable composition for this scene.",
        last_frame_prompt="Return to a near-identical composition so the clip can loop.",
        expected_video_key=(
            f"grok/{_safe_path_part(split.script_id)}/"
            f"{clip_index:02d}-{_safe_path_part(segment.segment_id)}.mp4"
        ),
    )


def _validate_duration_range(policy: GrokPromptPolicy) -> None:
    if policy.min_duration_seconds > policy.max_duration_seconds:
        msg = "min_duration_seconds must be less than or equal to max_duration_seconds"
        raise ValueError(msg)


def _safe_path_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-") or "clip"
