import pytest
from ai_shorts.agents.ass_generator import generate_ass_from_split
from ai_shorts.agents.ffmpeg_composer import (
    build_ffmpeg_composition_plan,
    run_ffmpeg_composition,
)
from ai_shorts.agents.splitter import SplitterPolicy, split_script
from ai_shorts.schemas.composition_manifest import (
    CompositionManifest,
    CompositionSegment,
    MediaRef,
)
from ai_shorts.schemas.script import Script, ScriptLine, ScriptScene


def _script() -> Script:
    return Script(
        id="script-phase3-001",
        template_id="benchmark-phase3-001",
        title="Phase 3 Integration Script",
        target_duration_ms=9000,
        scenes=[
            ScriptScene(
                index=0,
                visual_prompt="Open on the final result.",
                lines=[
                    ScriptLine(
                        speaker="narrator",
                        text="This hook explains the result before the setup.",
                        start_ms=0,
                        end_ms=4000,
                        emphasis_cue="hook",
                    )
                ],
            ),
            ScriptScene(
                index=1,
                visual_prompt="Show the proof in quick cuts.",
                lines=[
                    ScriptLine(
                        speaker="narrator",
                        text="Then the proof makes the format repeatable.",
                        start_ms=4000,
                        end_ms=9000,
                    )
                ],
            ),
        ],
    )


@pytest.mark.asyncio
async def test_phase3_pipeline_builds_ass_manifest_and_ffmpeg_plan() -> None:
    script_split = split_script(_script(), policy=SplitterPolicy(max_segment_chars=48))
    ass_document = generate_ass_from_split(script_split)
    manifest = CompositionManifest(
        script_id=script_split.script_id,
        output_ratio="9:16",
        fps=30,
        segments=[
            CompositionSegment(
                index=segment_index,
                video=MediaRef(
                    uri=f"assets/phase3-video-{segment_index:02d}.mp4",
                    mime_type="video/mp4",
                ),
                voiceover=MediaRef(
                    uri=f"assets/phase3-voice-{segment_index:02d}.wav",
                    mime_type="audio/wav",
                ),
                subtitle_ass="build/composition/script-phase3-001.ass",
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
            )
            for segment_index, segment in enumerate(script_split.segments)
        ],
    )
    plan = build_ffmpeg_composition_plan(
        manifest,
        output_uri="build/composition/script-phase3-001.mp4",
    )
    commands: list[list[str]] = []

    async def runner(command: list[str]) -> None:
        commands.append(command)

    result = await run_ffmpeg_composition(plan, runner=runner)

    assert ass_document.event_count == len(script_split.segments)
    assert "Dialogue: 0,0:00:00.00,0:00:04.00,Default,narrator" in ass_document.content
    assert len(plan.segment_commands) == len(manifest.segments)
    assert plan.duration_ms == script_split.target_duration_ms
    assert plan.concat_file_body.count("file 'build/composition/script-phase3-001-segment-") == len(
        manifest.segments
    )
    assert result.output_uri == "build/composition/script-phase3-001.mp4"
    assert result.commands_executed == len(manifest.segments) + 1
    assert commands[-1] == plan.final_command
