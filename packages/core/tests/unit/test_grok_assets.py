import pytest
from ai_shorts.agents.grok_assets import (
    GrokPromptPolicy,
    build_grok_clip_prompts,
    register_grok_video_assets,
)
from ai_shorts.schemas.script import ScriptSegment, ScriptSplit


def _split() -> ScriptSplit:
    return ScriptSplit(
        script_id="script-01",
        language="ko",
        target_duration_ms=5000,
        segments=[
            ScriptSegment(
                segment_id="segment-script-01-s00-l00-c00",
                script_id="script-01",
                scene_index=0,
                line_index=0,
                chunk_index=0,
                speaker="narrator",
                text="완성 장면을 먼저 보여줍니다.",
                start_ms=0,
                end_ms=2500,
                metadata={"scene_visual_prompt": "Open on the final result."},
            ),
            ScriptSegment(
                segment_id="segment-script-01-s01-l00-c00",
                script_id="script-01",
                scene_index=1,
                line_index=0,
                chunk_index=0,
                speaker="narrator",
                text="따라 할 이유를 설명합니다.",
                start_ms=2500,
                end_ms=5000,
                metadata={"scene_visual_prompt": "Show the proof."},
            ),
        ],
    )


def test_build_grok_clip_prompts_creates_one_prompt_per_segment() -> None:
    prompts = build_grok_clip_prompts(_split(), topic="AI pasta reveal")

    assert [prompt.clip_index for prompt in prompts] == [1, 2]
    assert prompts[0].segment_id == "segment-script-01-s00-l00-c00"
    assert "vertical 9:16" in prompts[0].prompt
    assert "AI pasta reveal" in prompts[0].prompt
    assert "Open on the final result." in prompts[0].prompt
    assert "No text overlay." in prompts[0].prompt
    assert prompts[0].expected_video_key == (
        "grok/script-01/01-segment-script-01-s00-l00-c00.mp4"
    )


def test_build_grok_clip_prompts_validates_duration_range() -> None:
    with pytest.raises(ValueError, match="min_duration_seconds"):
        build_grok_clip_prompts(
            _split(),
            topic="bad range",
            policy=GrokPromptPolicy(min_duration_seconds=15, max_duration_seconds=10),
        )


def test_register_grok_video_assets_maps_uris_to_segments() -> None:
    assets = register_grok_video_assets(
        _split(),
        [
            ".local_storage/grok/script-01/clip-01.mp4",
            ".local_storage/grok/script-01/clip-02.mp4",
        ],
    )

    assert [asset.segment_id for asset in assets] == [
        "segment-script-01-s00-l00-c00",
        "segment-script-01-s01-l00-c00",
    ]
    assert assets[0].media.uri == ".local_storage/grok/script-01/clip-01.mp4"
    assert assets[0].media.mime_type == "video/mp4"
    assert assets[0].media.duration_ms == 2500


def test_register_grok_video_assets_rejects_missing_or_mismatched_uris() -> None:
    with pytest.raises(RuntimeError, match="Expected 2 video URI"):
        register_grok_video_assets(_split(), ["one.mp4"])

    with pytest.raises(RuntimeError, match="Video URI is required"):
        register_grok_video_assets(_split(), ["one.mp4", " "])
