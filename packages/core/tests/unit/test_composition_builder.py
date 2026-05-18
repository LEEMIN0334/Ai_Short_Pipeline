import pytest
from ai_shorts.agents.composition_builder import (
    CompositionBuilderPolicy,
    build_composition_manifest,
)
from ai_shorts.agents.grok_assets import GrokVideoAsset
from ai_shorts.agents.voiceover import VoiceoverAsset
from ai_shorts.schemas.composition_manifest import MediaRef
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
                text="첫 장면입니다.",
                start_ms=0,
                end_ms=2500,
            ),
            ScriptSegment(
                segment_id="segment-script-01-s01-l00-c00",
                script_id="script-01",
                scene_index=1,
                line_index=0,
                chunk_index=0,
                speaker="narrator",
                text="두 번째 장면입니다.",
                start_ms=2500,
                end_ms=5000,
            ),
        ],
    )


def _video_assets() -> list[GrokVideoAsset]:
    return [
        GrokVideoAsset(
            segment_id="segment-script-01-s00-l00-c00",
            scene_index=0,
            clip_index=1,
            media=MediaRef(uri="grok/clip-01.mp4", mime_type="video/mp4", duration_ms=2500),
        ),
        GrokVideoAsset(
            segment_id="segment-script-01-s01-l00-c00",
            scene_index=1,
            clip_index=2,
            media=MediaRef(uri="grok/clip-02.mp4", mime_type="video/mp4", duration_ms=2500),
        ),
    ]


def _voiceover_assets() -> list[VoiceoverAsset]:
    return [
        VoiceoverAsset(
            segment_id="segment-script-01-s00-l00-c00",
            scene_index=0,
            line_index=0,
            chunk_index=0,
            text="첫 장면입니다.",
            media=MediaRef(uri="voice/clip-01.wav", mime_type="audio/wav", duration_ms=2500),
        ),
        VoiceoverAsset(
            segment_id="segment-script-01-s01-l00-c00",
            scene_index=1,
            line_index=0,
            chunk_index=0,
            text="두 번째 장면입니다.",
            media=MediaRef(uri="voice/clip-02.wav", mime_type="audio/wav", duration_ms=2500),
        ),
    ]


def test_build_composition_manifest_combines_assets_by_segment_id() -> None:
    manifest = build_composition_manifest(
        _split(),
        video_assets=_video_assets(),
        voiceover_assets=_voiceover_assets(),
        policy=CompositionBuilderPolicy(subtitle_ass_uri="build/subtitles/script-01.ass"),
    )

    assert manifest.script_id == "script-01"
    assert manifest.output_ratio == "9:16"
    assert manifest.fps == 30
    assert [segment.index for segment in manifest.segments] == [0, 1]
    assert manifest.segments[0].video.uri == "grok/clip-01.mp4"
    assert manifest.segments[0].voiceover is not None
    assert manifest.segments[0].voiceover.uri == "voice/clip-01.wav"
    assert manifest.segments[0].subtitle_ass == "build/subtitles/script-01.ass"
    assert [(segment.start_ms, segment.end_ms) for segment in manifest.segments] == [
        (0, 2500),
        (2500, 5000),
    ]


def test_build_composition_manifest_can_skip_optional_voiceover() -> None:
    manifest = build_composition_manifest(
        _split(),
        video_assets=_video_assets(),
        policy=CompositionBuilderPolicy(require_voiceover=False),
    )

    assert [segment.voiceover for segment in manifest.segments] == [None, None]


def test_build_composition_manifest_rejects_missing_assets() -> None:
    with pytest.raises(RuntimeError, match="Missing video asset"):
        build_composition_manifest(
            _split(),
            video_assets=_video_assets()[:1],
            voiceover_assets=_voiceover_assets(),
        )

    with pytest.raises(RuntimeError, match="Missing voiceover asset"):
        build_composition_manifest(
            _split(),
            video_assets=_video_assets(),
            voiceover_assets=_voiceover_assets()[:1],
        )


def test_build_composition_manifest_rejects_duplicate_assets() -> None:
    duplicate = [_video_assets()[0], _video_assets()[0]]

    with pytest.raises(RuntimeError, match="Duplicate video asset"):
        build_composition_manifest(
            _split(),
            video_assets=duplicate,
            voiceover_assets=_voiceover_assets(),
        )
