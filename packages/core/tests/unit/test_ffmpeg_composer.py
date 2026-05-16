import pytest
from ai_shorts.agents.ffmpeg_composer import (
    FFmpegComposerPolicy,
    build_ffmpeg_composition_plan,
    run_ffmpeg_composition,
)
from ai_shorts.schemas.composition_manifest import (
    CompositionManifest,
    CompositionSegment,
    MediaRef,
)


def _manifest() -> CompositionManifest:
    return CompositionManifest(
        script_id="script-01",
        output_ratio="9:16",
        fps=30,
        segments=[
            CompositionSegment(
                index=0,
                video=MediaRef(uri="assets/video-00.mp4", mime_type="video/mp4"),
                voiceover=MediaRef(uri="assets/voice-00.wav", mime_type="audio/wav"),
                subtitle_ass="assets/subtitles.ass",
                start_ms=0,
                end_ms=2500,
            ),
            CompositionSegment(
                index=1,
                video=MediaRef(uri="assets/video-01.mp4", mime_type="video/mp4"),
                start_ms=2500,
                end_ms=6000,
            ),
        ],
    )


def test_build_ffmpeg_composition_plan_creates_segment_and_concat_commands() -> None:
    plan = build_ffmpeg_composition_plan(_manifest(), output_uri="build/final.mp4")

    assert plan.script_id == "script-01"
    assert plan.output_uri == "build/final.mp4"
    assert plan.concat_file_uri == "build/composition/script-01-concat.txt"
    assert plan.concat_file_body == (
        "file 'build/composition/script-01-segment-000.mp4'\n"
        "file 'build/composition/script-01-segment-001.mp4'\n"
    )
    assert len(plan.segment_commands) == 2
    first_command = plan.segment_commands[0].command
    assert first_command[:6] == [
        "ffmpeg",
        "-y",
        "-i",
        "assets/video-00.mp4",
        "-i",
        "assets/voice-00.wav",
    ]
    assert "-vf" in first_command
    assert any("subtitles='assets/subtitles.ass'" in arg for arg in first_command)
    assert "-map" in first_command
    assert "1:a:0" in first_command
    assert plan.segment_commands[1].command.count("-an") == 1
    assert plan.final_command == [
        "ffmpeg",
        "-y",
        "-safe",
        "0",
        "-f",
        "concat",
        "-i",
        "build/composition/script-01-concat.txt",
        "-c",
        "copy",
        "build/final.mp4",
    ]


def test_build_ffmpeg_composition_plan_applies_policy() -> None:
    plan = build_ffmpeg_composition_plan(
        _manifest(),
        output_uri="out.mp4",
        policy=FFmpegComposerPolicy(
            ffmpeg_bin="/usr/bin/ffmpeg",
            work_dir_uri="tmp/render",
            output_width=720,
            output_height=1280,
            crf=20,
            overwrite=False,
        ),
    )

    first_command = plan.segment_commands[0].command
    assert first_command[0] == "/usr/bin/ffmpeg"
    assert "-y" not in first_command
    assert any(
        "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280" in arg
        for arg in first_command
    )
    assert "20" in first_command
    assert plan.concat_file_uri == "tmp/render/script-01-concat.txt"


def test_build_ffmpeg_composition_plan_rejects_empty_manifest() -> None:
    manifest = _manifest()
    manifest.segments = []

    with pytest.raises(RuntimeError, match="at least one segment"):
        build_ffmpeg_composition_plan(manifest, output_uri="out.mp4")


def test_build_ffmpeg_composition_plan_rejects_invalid_timing() -> None:
    manifest = _manifest()
    manifest.segments[0].start_ms = 1000
    manifest.segments[0].end_ms = 1000

    with pytest.raises(RuntimeError, match="end_ms must be greater than start_ms"):
        build_ffmpeg_composition_plan(manifest, output_uri="out.mp4")


@pytest.mark.asyncio
async def test_run_ffmpeg_composition_uses_injected_runner() -> None:
    plan = build_ffmpeg_composition_plan(_manifest(), output_uri="build/final.mp4")
    commands: list[list[str]] = []

    async def runner(command: list[str]) -> None:
        commands.append(command)

    result = await run_ffmpeg_composition(plan, runner=runner)

    assert result.script_id == "script-01"
    assert result.output_uri == "build/final.mp4"
    assert result.commands_executed == 3
    assert commands == [
        plan.segment_commands[0].command,
        plan.segment_commands[1].command,
        plan.final_command,
    ]
