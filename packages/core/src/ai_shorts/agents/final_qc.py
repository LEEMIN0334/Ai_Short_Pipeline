from pydantic import BaseModel, Field

from ai_shorts.schemas.composition_manifest import CompositionManifest, MediaRef
from ai_shorts.schemas.qc_report import QCReport, QCScore


class FinalQCPolicy(BaseModel):
    """Final rendered-video QC thresholds before human approval."""

    required_ratio: str = "9:16"
    required_mime_type: str = "video/mp4"
    min_duration_ms: int = Field(default=5_000, gt=0)
    max_duration_ms: int = Field(default=60_000, gt=0)
    pass_threshold: float = Field(default=0.85, ge=0, le=1)
    require_subtitles: bool = True
    require_voiceover: bool = True


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
