import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path

from pydantic import BaseModel, Field

from ai_shorts.schemas.composition_manifest import CompositionManifest, CompositionSegment

FFmpegRunner = Callable[[list[str]], Awaitable[None]]


class FFmpegComposerPolicy(BaseModel):
    """FFmpeg defaults for vertical short composition."""

    ffmpeg_bin: str = "ffmpeg"
    work_dir_uri: str = "build/composition"
    output_width: int = Field(default=1080, gt=0)
    output_height: int = Field(default=1920, gt=0)
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    preset: str = "veryfast"
    crf: int = Field(default=23, ge=0, le=51)
    overwrite: bool = True


class FFmpegSegmentCommand(BaseModel):
    segment_index: int = Field(ge=0)
    output_uri: str
    command: list[str]


class FFmpegCompositionPlan(BaseModel):
    script_id: str
    output_uri: str
    concat_file_uri: str
    concat_file_body: str
    segment_commands: list[FFmpegSegmentCommand]
    final_command: list[str]
    duration_ms: int = Field(gt=0)


class FFmpegRenderResult(BaseModel):
    script_id: str
    output_uri: str
    commands_executed: int = Field(ge=0)
    concat_file_uri: str
    output_exists: bool = False


class FFmpegRenderFiles(BaseModel):
    concat_file_path: str
    output_path: str
    prepared_directories: list[str]


def build_ffmpeg_composition_plan(
    manifest: CompositionManifest,
    *,
    output_uri: str,
    policy: FFmpegComposerPolicy | None = None,
) -> FFmpegCompositionPlan:
    """Build deterministic FFmpeg commands for rendering a composition manifest."""

    active_policy = policy or FFmpegComposerPolicy()
    if not manifest.segments:
        raise RuntimeError("Composition manifest must contain at least one segment")

    segment_commands = [
        _segment_command(manifest, segment, active_policy)
        for segment in sorted(manifest.segments, key=lambda item: item.index)
    ]
    concat_file_uri = f"{active_policy.work_dir_uri}/{manifest.script_id}-concat.txt"
    concat_file_body = "".join(
        f"file '{_escape_concat_path(command.output_uri)}'\n" for command in segment_commands
    )
    final_command = [
        *_base_command(active_policy),
        "-safe",
        "0",
        "-f",
        "concat",
        "-i",
        concat_file_uri,
        "-c",
        "copy",
        output_uri,
    ]

    return FFmpegCompositionPlan(
        script_id=manifest.script_id,
        output_uri=output_uri,
        concat_file_uri=concat_file_uri,
        concat_file_body=concat_file_body,
        segment_commands=segment_commands,
        final_command=final_command,
        duration_ms=sum(segment.end_ms - segment.start_ms for segment in manifest.segments),
    )


async def run_ffmpeg_composition(
    plan: FFmpegCompositionPlan,
    *,
    runner: FFmpegRunner | None = None,
    prepare_files: bool = False,
    verify_output: bool = False,
    root: Path | None = None,
) -> FFmpegRenderResult:
    """Run every FFmpeg command in a composition plan."""

    if prepare_files:
        prepare_ffmpeg_render_files(plan, root=root)

    active_runner = runner or _run_subprocess
    for segment_command in plan.segment_commands:
        await active_runner(segment_command.command)
    await active_runner(plan.final_command)

    output_exists = _resolve_uri(plan.output_uri, root=root).exists()
    if verify_output and not output_exists:
        msg = f"FFmpeg output was not created: {plan.output_uri}"
        raise RuntimeError(msg)

    return FFmpegRenderResult(
        script_id=plan.script_id,
        output_uri=plan.output_uri,
        concat_file_uri=plan.concat_file_uri,
        commands_executed=len(plan.segment_commands) + 1,
        output_exists=output_exists,
    )


def prepare_ffmpeg_render_files(
    plan: FFmpegCompositionPlan,
    *,
    root: Path | None = None,
) -> FFmpegRenderFiles:
    """Create render directories and write the FFmpeg concat file."""

    prepared_directories: set[Path] = set()
    concat_file = _resolve_uri(plan.concat_file_uri, root=root)
    output_file = _resolve_uri(plan.output_uri, root=root)

    _mkdir(concat_file.parent, prepared_directories)
    _mkdir(output_file.parent, prepared_directories)
    for segment_command in plan.segment_commands:
        _mkdir(_resolve_uri(segment_command.output_uri, root=root).parent, prepared_directories)

    concat_file.write_text(plan.concat_file_body, encoding="utf-8")
    return FFmpegRenderFiles(
        concat_file_path=str(concat_file),
        output_path=str(output_file),
        prepared_directories=sorted(str(path) for path in prepared_directories),
    )


def _segment_command(
    manifest: CompositionManifest,
    segment: CompositionSegment,
    policy: FFmpegComposerPolicy,
) -> FFmpegSegmentCommand:
    if segment.end_ms <= segment.start_ms:
        raise RuntimeError("Composition segment end_ms must be greater than start_ms")

    output_uri = f"{policy.work_dir_uri}/{manifest.script_id}-segment-{segment.index:03d}.mp4"
    command = [
        *_base_command(policy),
        "-i",
        segment.video.uri,
    ]
    if segment.voiceover is not None:
        command.extend(["-i", segment.voiceover.uri])

    command.extend(
        [
            "-t",
            _duration_seconds(segment),
            "-vf",
            _video_filter(segment, policy),
            "-r",
            str(manifest.fps),
            "-map",
            "0:v:0",
        ]
    )
    if segment.voiceover is not None:
        command.extend(["-map", "1:a:0", "-c:a", policy.audio_codec])
    else:
        command.append("-an")

    command.extend(
        [
            "-c:v",
            policy.video_codec,
            "-preset",
            policy.preset,
            "-crf",
            str(policy.crf),
            "-pix_fmt",
            "yuv420p",
            output_uri,
        ]
    )
    return FFmpegSegmentCommand(
        segment_index=segment.index,
        output_uri=output_uri,
        command=command,
    )


def _base_command(policy: FFmpegComposerPolicy) -> list[str]:
    command = [policy.ffmpeg_bin]
    if policy.overwrite:
        command.append("-y")
    return command


def _video_filter(segment: CompositionSegment, policy: FFmpegComposerPolicy) -> str:
    filters = [
        (
            f"scale={policy.output_width}:{policy.output_height}:"
            "force_original_aspect_ratio=increase"
        ),
        f"crop={policy.output_width}:{policy.output_height}",
        "setsar=1",
    ]
    if segment.subtitle_ass:
        filters.append(f"subtitles='{_escape_filter_path(segment.subtitle_ass)}'")
    return ",".join(filters)


def _duration_seconds(segment: CompositionSegment) -> str:
    return f"{(segment.end_ms - segment.start_ms) / 1000:.3f}"


def _escape_concat_path(path: str) -> str:
    return path.replace("'", "'\\''")


def _escape_filter_path(path: str) -> str:
    return path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


async def _run_subprocess(command: list[str]) -> None:
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(f"FFmpeg command failed: {stderr.decode(errors='replace')}")


def _resolve_uri(uri: str, *, root: Path | None) -> Path:
    path = Path(uri)
    if path.is_absolute():
        return path
    return (root or Path.cwd()) / path


def _mkdir(path: Path, prepared_directories: set[Path]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    prepared_directories.add(path)
