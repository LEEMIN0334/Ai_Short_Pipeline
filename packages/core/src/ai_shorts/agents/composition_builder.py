from pydantic import BaseModel, Field

from ai_shorts.agents.grok_assets import GrokVideoAsset
from ai_shorts.agents.voiceover import VoiceoverAsset
from ai_shorts.schemas.composition_manifest import CompositionManifest, CompositionSegment, MediaRef
from ai_shorts.schemas.script import ScriptSegment, ScriptSplit


class CompositionBuilderPolicy(BaseModel):
    """Defaults for assembling render-ready composition manifests."""

    output_ratio: str = "9:16"
    fps: int = Field(default=30, gt=0)
    subtitle_ass_uri: str | None = None
    require_voiceover: bool = True


def build_composition_manifest(
    split: ScriptSplit,
    *,
    video_assets: list[GrokVideoAsset],
    voiceover_assets: list[VoiceoverAsset] | None = None,
    policy: CompositionBuilderPolicy | None = None,
) -> CompositionManifest:
    """Combine video, voiceover, and subtitle assets into a render manifest."""

    active_policy = policy or CompositionBuilderPolicy()
    if not split.segments:
        raise RuntimeError("Script split must contain at least one segment")

    videos = _video_asset_map(video_assets)
    voiceovers = _voiceover_asset_map(voiceover_assets or [])
    segments = [
        _composition_segment(
            index=index,
            segment=segment,
            video=_required_video(videos, segment),
            voiceover=_voiceover_for_segment(
                voiceovers,
                segment,
                require_voiceover=active_policy.require_voiceover,
            ),
            subtitle_ass=active_policy.subtitle_ass_uri,
        )
        for index, segment in enumerate(split.segments)
    ]
    return CompositionManifest(
        script_id=split.script_id,
        output_ratio=active_policy.output_ratio,
        fps=active_policy.fps,
        segments=segments,
    )


def _composition_segment(
    *,
    index: int,
    segment: ScriptSegment,
    video: MediaRef,
    voiceover: MediaRef | None,
    subtitle_ass: str | None,
) -> CompositionSegment:
    if segment.end_ms <= segment.start_ms:
        raise RuntimeError(f"Invalid segment timing: {segment.segment_id}")
    return CompositionSegment(
        index=index,
        video=video,
        voiceover=voiceover,
        subtitle_ass=subtitle_ass,
        start_ms=segment.start_ms,
        end_ms=segment.end_ms,
    )


def _video_asset_map(assets: list[GrokVideoAsset]) -> dict[str, GrokVideoAsset]:
    mapped: dict[str, GrokVideoAsset] = {}
    for asset in assets:
        if asset.segment_id in mapped:
            msg = f"Duplicate video asset for segment {asset.segment_id}"
            raise RuntimeError(msg)
        mapped[asset.segment_id] = asset
    return mapped


def _voiceover_asset_map(assets: list[VoiceoverAsset]) -> dict[str, VoiceoverAsset]:
    mapped: dict[str, VoiceoverAsset] = {}
    for asset in assets:
        if asset.segment_id in mapped:
            msg = f"Duplicate voiceover asset for segment {asset.segment_id}"
            raise RuntimeError(msg)
        mapped[asset.segment_id] = asset
    return mapped


def _required_video(
    assets: dict[str, GrokVideoAsset],
    segment: ScriptSegment,
) -> MediaRef:
    asset = assets.get(segment.segment_id)
    if asset is None:
        msg = f"Missing video asset for segment {segment.segment_id}"
        raise RuntimeError(msg)
    return asset.media


def _voiceover_for_segment(
    assets: dict[str, VoiceoverAsset],
    segment: ScriptSegment,
    *,
    require_voiceover: bool,
) -> MediaRef | None:
    asset = assets.get(segment.segment_id)
    if asset is None:
        if require_voiceover:
            msg = f"Missing voiceover asset for segment {segment.segment_id}"
            raise RuntimeError(msg)
        return None
    return asset.media
