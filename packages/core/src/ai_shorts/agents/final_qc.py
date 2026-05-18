import asyncio
import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ai_shorts.schemas.composition_manifest import CompositionManifest, MediaRef
from ai_shorts.schemas.qc_report import QCReport, QCScore

FFprobeRunner = Callable[[list[str]], Awaitable[str]]


class FinalQCPolicy(BaseModel):
    """Final rendered-video QC thresholds before human approval."""

    required_ratio: str = "9:16"
    required_mime_type: str = "video/mp4"
    min_duration_ms: int = Field(default=5_000, gt=0)
    max_duration_ms: int = Field(default=60_000, gt=0)
    pass_threshold: float = Field(default=0.85, ge=0, le=1)
    require_subtitles: bool = True
    require_voiceover: bool = True


class RenderFileQCPolicy(FinalQCPolicy):
    """QC thresholds for probing a rendered video file."""

    ffprobe_bin: str = "ffprobe"
    expected_width: int = Field(default=1080, gt=0)
    expected_height: int = Field(default=1920, gt=0)
    duration_tolerance_ms: int = Field(default=750, ge=0)


def evaluate_final_qc(
    manifest: CompositionManifest,
    rendered_video: MediaRef,
    *,
    target_id: str | None = None,
    policy: FinalQCPolicy | None = None,
) -> QCReport:
    """Evaluate a rendered composition before it enters the approval queue."""

    active_policy = policy or FinalQCPolicy()
    scores = [
        _ratio_score(manifest, active_policy),
        _duration_score(manifest, rendered_video, active_policy),
        _subtitle_score(manifest, active_policy),
        _voiceover_score(manifest, active_policy),
        _media_ref_score(manifest, rendered_video, active_policy),
    ]
    overall_score = sum(score.score for score in scores) / len(scores)
    required_fixes = [score.reason for score in scores if score.score < 1]

    return QCReport(
        target_id=target_id or manifest.script_id,
        overall_score=round(overall_score, 3),
        scores=scores,
        passed=overall_score >= active_policy.pass_threshold and not required_fixes,
        required_fixes=required_fixes,
    )


async def evaluate_render_file_qc(
    manifest: CompositionManifest,
    rendered_video: MediaRef,
    *,
    target_id: str | None = None,
    policy: RenderFileQCPolicy | None = None,
    runner: FFprobeRunner | None = None,
    root: Path | None = None,
) -> QCReport:
    """Evaluate an actual rendered file using ffprobe metadata."""

    active_policy = policy or RenderFileQCPolicy()
    file_score = _render_file_exists_score(rendered_video, root=root)
    if file_score.score == 0:
        return _report_from_scores(
            target_id=target_id or manifest.script_id,
            scores=[
                _ratio_score(manifest, active_policy),
                file_score,
                _subtitle_score(manifest, active_policy),
                _voiceover_score(manifest, active_policy),
                _media_ref_score(manifest, rendered_video, active_policy),
            ],
            pass_threshold=active_policy.pass_threshold,
        )

    probe = await _probe_rendered_file(
        rendered_video,
        policy=active_policy,
        runner=runner,
        root=root,
    )
    scores = [
        _ratio_score(manifest, active_policy),
        file_score,
        _probe_duration_score(manifest, probe, active_policy),
        _probe_resolution_score(probe, active_policy),
        _probe_audio_score(probe, active_policy),
        _subtitle_score(manifest, active_policy),
        _voiceover_score(manifest, active_policy),
        _media_ref_score(manifest, rendered_video, active_policy),
    ]
    return _report_from_scores(
        target_id=target_id or manifest.script_id,
        scores=scores,
        pass_threshold=active_policy.pass_threshold,
    )


def _ratio_score(manifest: CompositionManifest, policy: FinalQCPolicy) -> QCScore:
    if manifest.output_ratio == policy.required_ratio:
        return QCScore(name="output_ratio", score=1, reason="Output ratio matches requirement.")
    return QCScore(
        name="output_ratio",
        score=0,
        reason=f"Expected output ratio {policy.required_ratio}, got {manifest.output_ratio}.",
    )


def _duration_score(
    manifest: CompositionManifest,
    rendered_video: MediaRef,
    policy: FinalQCPolicy,
) -> QCScore:
    manifest_duration_ms = sum(segment.end_ms - segment.start_ms for segment in manifest.segments)
    rendered_duration_ms = rendered_video.duration_ms
    duration_ms = rendered_duration_ms or manifest_duration_ms

    if not manifest.segments:
        return QCScore(name="duration", score=0, reason="Composition has no segments.")
    if rendered_duration_ms is None:
        return QCScore(name="duration", score=0.7, reason="Rendered duration is missing.")
    if policy.min_duration_ms <= duration_ms <= policy.max_duration_ms:
        return QCScore(name="duration", score=1, reason="Rendered duration is in range.")
    return QCScore(
        name="duration",
        score=0,
        reason=(
            f"Rendered duration {duration_ms}ms must be between "
            f"{policy.min_duration_ms}ms and {policy.max_duration_ms}ms."
        ),
    )


def _subtitle_score(manifest: CompositionManifest, policy: FinalQCPolicy) -> QCScore:
    if not policy.require_subtitles:
        return QCScore(name="subtitles", score=1, reason="Subtitles are optional.")
    if manifest.segments and all(segment.subtitle_ass for segment in manifest.segments):
        return QCScore(name="subtitles", score=1, reason="All segments include subtitles.")
    return QCScore(name="subtitles", score=0, reason="Every segment must include ASS subtitles.")


def _voiceover_score(manifest: CompositionManifest, policy: FinalQCPolicy) -> QCScore:
    if not policy.require_voiceover:
        return QCScore(name="voiceover", score=1, reason="Voiceover is optional.")
    if manifest.segments and all(segment.voiceover is not None for segment in manifest.segments):
        return QCScore(name="voiceover", score=1, reason="All segments include voiceover.")
    return QCScore(name="voiceover", score=0, reason="Every segment must include voiceover audio.")


def _media_ref_score(
    manifest: CompositionManifest,
    rendered_video: MediaRef,
    policy: FinalQCPolicy,
) -> QCScore:
    missing_video_refs = [segment.index for segment in manifest.segments if not segment.video.uri]
    if missing_video_refs:
        return QCScore(
            name="media_refs",
            score=0,
            reason=f"Segments missing video references: {missing_video_refs}.",
        )
    if rendered_video.mime_type != policy.required_mime_type:
        return QCScore(
            name="media_refs",
            score=0,
            reason=(
                f"Rendered mime type must be {policy.required_mime_type}, "
                f"got {rendered_video.mime_type}."
            ),
        )
    if not rendered_video.uri:
        return QCScore(name="media_refs", score=0, reason="Rendered video URI is missing.")
    return QCScore(name="media_refs", score=1, reason="Rendered media references are valid.")


def _report_from_scores(
    *,
    target_id: str,
    scores: list[QCScore],
    pass_threshold: float,
) -> QCReport:
    overall_score = sum(score.score for score in scores) / len(scores)
    required_fixes = [score.reason for score in scores if score.score < 1]
    return QCReport(
        target_id=target_id,
        overall_score=round(overall_score, 3),
        scores=scores,
        passed=overall_score >= pass_threshold and not required_fixes,
        required_fixes=required_fixes,
    )


def _render_file_exists_score(rendered_video: MediaRef, *, root: Path | None) -> QCScore:
    path = _resolve_uri(rendered_video.uri, root=root)
    if path.exists():
        return QCScore(name="render_file", score=1, reason="Rendered file exists.")
    return QCScore(
        name="render_file",
        score=0,
        reason=f"Rendered file does not exist: {rendered_video.uri}.",
    )


async def _probe_rendered_file(
    rendered_video: MediaRef,
    *,
    policy: RenderFileQCPolicy,
    runner: FFprobeRunner | None,
    root: Path | None,
) -> dict[str, Any]:
    command = [
        policy.ffprobe_bin,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(_resolve_uri(rendered_video.uri, root=root)),
    ]
    output = await (runner or _run_ffprobe)(command)
    loaded = json.loads(output)
    if not isinstance(loaded, dict):
        msg = "ffprobe output must be a JSON object"
        raise RuntimeError(msg)
    return loaded


async def _run_ffprobe(command: list[str]) -> str:
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {stderr.decode(errors='replace')}")
    return stdout.decode(errors="replace")


def _probe_duration_score(
    manifest: CompositionManifest,
    probe: dict[str, Any],
    policy: RenderFileQCPolicy,
) -> QCScore:
    expected_ms = sum(segment.end_ms - segment.start_ms for segment in manifest.segments)
    duration_ms = _probe_duration_ms(probe)
    if duration_ms is None:
        return QCScore(name="probe_duration", score=0, reason="ffprobe duration is missing.")
    if not policy.min_duration_ms <= duration_ms <= policy.max_duration_ms:
        return QCScore(
            name="probe_duration",
            score=0,
            reason=(
                f"ffprobe duration {duration_ms}ms must be between "
                f"{policy.min_duration_ms}ms and {policy.max_duration_ms}ms."
            ),
        )
    drift = abs(duration_ms - expected_ms)
    if drift <= policy.duration_tolerance_ms:
        return QCScore(name="probe_duration", score=1, reason="ffprobe duration matches plan.")
    return QCScore(
        name="probe_duration",
        score=0,
        reason=(
            f"ffprobe duration drift {drift}ms exceeds tolerance "
            f"{policy.duration_tolerance_ms}ms."
        ),
    )


def _probe_resolution_score(probe: dict[str, Any], policy: RenderFileQCPolicy) -> QCScore:
    video = _first_stream(probe, "video")
    if video is None:
        return QCScore(name="probe_resolution", score=0, reason="ffprobe found no video stream.")
    width = _int_value(video.get("width"))
    height = _int_value(video.get("height"))
    if width == policy.expected_width and height == policy.expected_height:
        return QCScore(name="probe_resolution", score=1, reason="Rendered resolution matches.")
    return QCScore(
        name="probe_resolution",
        score=0,
        reason=(
            f"Rendered resolution must be {policy.expected_width}x{policy.expected_height}, "
            f"got {width}x{height}."
        ),
    )


def _probe_audio_score(probe: dict[str, Any], policy: RenderFileQCPolicy) -> QCScore:
    if not policy.require_voiceover:
        return QCScore(name="probe_audio", score=1, reason="Audio stream is optional.")
    if _first_stream(probe, "audio") is not None:
        return QCScore(name="probe_audio", score=1, reason="Rendered file includes audio.")
    return QCScore(name="probe_audio", score=0, reason="ffprobe found no audio stream.")


def _probe_duration_ms(probe: dict[str, Any]) -> int | None:
    format_obj = probe.get("format")
    if not isinstance(format_obj, dict):
        return None
    duration = format_obj.get("duration")
    if not isinstance(duration, str | int | float):
        return None
    try:
        return round(float(duration) * 1000)
    except ValueError:
        return None


def _first_stream(probe: dict[str, Any], codec_type: str) -> dict[str, Any] | None:
    streams = probe.get("streams")
    if not isinstance(streams, list):
        return None
    for stream in streams:
        if isinstance(stream, dict) and stream.get("codec_type") == codec_type:
            return stream
    return None


def _int_value(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _resolve_uri(uri: str, *, root: Path | None) -> Path:
    path = Path(uri)
    if path.is_absolute():
        return path
    return (root or Path.cwd()) / path
