import pytest
from ai_shorts.agents.production_handoff import ProductionHandoffPolicy, build_production_handoff
from ai_shorts.agents.voiceover import VoiceoverAsset
from ai_shorts.schemas.composition_manifest import MediaRef
from ai_shorts.schemas.script import Script, ScriptLine, ScriptScene


def _script() -> Script:
    return Script(
        id="script-handoff-001",
        template_id="benchmark-001",
        title="Production Handoff Script",
        target_duration_ms=6000,
        scenes=[
            ScriptScene(
                index=0,
                visual_prompt="Open on the finished result.",
                lines=[
                    ScriptLine(
                        speaker="narrator",
                        text="Show the result first.",
                        start_ms=0,
                        end_ms=3000,
                    )
                ],
            ),
            ScriptScene(
                index=1,
                visual_prompt="Show the proof.",
                lines=[
                    ScriptLine(
                        speaker="narrator",
                        text="Then explain why it works.",
                        start_ms=3000,
                        end_ms=6000,
                    )
                ],
            ),
        ],
    )


def _voiceovers() -> list[VoiceoverAsset]:
    return [
        VoiceoverAsset(
            segment_id="segment-script-handoff-001-s00-l00-c00",
            scene_index=0,
            line_index=0,
            chunk_index=0,
            text="Show the result first.",
            media=MediaRef(uri="voice/00.wav", mime_type="audio/wav", duration_ms=3000),
        ),
        VoiceoverAsset(
            segment_id="segment-script-handoff-001-s01-l00-c00",
            scene_index=1,
            line_index=0,
            chunk_index=0,
            text="Then explain why it works.",
            media=MediaRef(uri="voice/01.wav", mime_type="audio/wav", duration_ms=3000),
        ),
    ]


def test_build_production_handoff_creates_render_ready_artifacts() -> None:
    handoff = build_production_handoff(
        _script(),
        topic="AI pasta reveal",
        video_uris=["grok/00.mp4", "grok/01.mp4"],
        voiceover_assets=_voiceovers(),
        policy=ProductionHandoffPolicy(
            subtitle_ass_uri="build/subtitles/script-handoff-001.ass",
            output_uri="build/render/script-handoff-001.mp4",
        ),
    )

    assert handoff.split.script_id == "script-handoff-001"
    assert handoff.ass_document.event_count == 2
    assert len(handoff.grok_prompts) == 2
    assert handoff.manifest.segments[0].video.uri == "grok/00.mp4"
    assert handoff.manifest.segments[0].voiceover is not None
    assert handoff.manifest.segments[0].subtitle_ass == "build/subtitles/script-handoff-001.ass"
    assert handoff.ffmpeg_plan.output_uri == "build/render/script-handoff-001.mp4"
    assert handoff.ffmpeg_plan.duration_ms == 6000
    assert handoff.final_qc.passed is True


def test_build_production_handoff_can_prepare_silent_manifest() -> None:
    handoff = build_production_handoff(
        _script(),
        topic="silent preview",
        video_uris=["grok/00.mp4", "grok/01.mp4"],
        policy=ProductionHandoffPolicy(require_voiceover=False),
    )

    assert [segment.voiceover for segment in handoff.manifest.segments] == [None, None]
    assert handoff.final_qc.passed is True


def test_build_production_handoff_rejects_missing_manual_video_uri() -> None:
    with pytest.raises(RuntimeError, match="Expected 2 video URI"):
        build_production_handoff(
            _script(),
            topic="missing video",
            video_uris=["grok/00.mp4"],
            voiceover_assets=_voiceovers(),
        )
