from pydantic import BaseModel, Field

from ai_shorts.agents.ass_generator import ASSDocument, generate_ass_from_split
from ai_shorts.agents.composition_builder import (
    CompositionBuilderPolicy,
    build_composition_manifest,
)
from ai_shorts.agents.ffmpeg_composer import FFmpegCompositionPlan, build_ffmpeg_composition_plan
from ai_shorts.agents.final_qc import FinalQCPolicy, evaluate_final_qc
from ai_shorts.agents.grok_assets import (
    GrokClipPrompt,
    GrokVideoAsset,
    build_grok_clip_prompts,
    register_grok_video_assets,
)
from ai_shorts.agents.splitter import SplitterPolicy, split_script
from ai_shorts.agents.voiceover import VoiceoverAsset
from ai_shorts.schemas.composition_manifest import CompositionManifest, MediaRef
from ai_shorts.schemas.qc_report import QCReport
from ai_shorts.schemas.script import Script, ScriptSplit


class ProductionHandoffPolicy(BaseModel):
    """Defaults for packaging a script into render-ready production artifacts."""

    subtitle_ass_uri: str | None = None
    output_uri: str | None = None
    output_ratio: str = "9:16"
    fps: int = Field(default=30, gt=0)
    require_voiceover: bool = True
    splitter_policy: SplitterPolicy = Field(default_factory=SplitterPolicy)
    qc_policy: FinalQCPolicy = Field(default_factory=FinalQCPolicy)


class ProductionHandoff(BaseModel):
    script: Script
    split: ScriptSplit
    ass_document: ASSDocument
    grok_prompts: list[GrokClipPrompt]
    video_assets: list[GrokVideoAsset]
    voiceover_assets: list[VoiceoverAsset] = Field(default_factory=list)
    manifest: CompositionManifest
    ffmpeg_plan: FFmpegCompositionPlan
    final_qc: QCReport


def build_production_handoff(
    script: Script,
    *,
    topic: str,
    video_uris: list[str],
    voiceover_assets: list[VoiceoverAsset] | None = None,
    policy: ProductionHandoffPolicy | None = None,
) -> ProductionHandoff:
    """Build render-ready artifacts from a script and manually supplied video assets."""

    active_policy = policy or ProductionHandoffPolicy()
    split = split_script(script, policy=active_policy.splitter_policy)
    ass_document = generate_ass_from_split(split)
    subtitle_ass_uri = active_policy.subtitle_ass_uri or f"build/composition/{script.id}.ass"
    output_uri = active_policy.output_uri or f"build/composition/{script.id}-final.mp4"
    grok_prompts = build_grok_clip_prompts(split, topic=topic)
    video_assets = register_grok_video_assets(split, video_uris)
    voiceovers = voiceover_assets or []
    manifest = build_composition_manifest(
        split,
        video_assets=video_assets,
        voiceover_assets=voiceovers,
        policy=CompositionBuilderPolicy(
            output_ratio=active_policy.output_ratio,
            fps=active_policy.fps,
            subtitle_ass_uri=subtitle_ass_uri,
            require_voiceover=active_policy.require_voiceover,
        ),
    )
    ffmpeg_plan = build_ffmpeg_composition_plan(manifest, output_uri=output_uri)
    qc_policy = active_policy.qc_policy.model_copy(
        update={"require_voiceover": active_policy.require_voiceover}
    )
    final_qc = evaluate_final_qc(
        manifest,
        MediaRef(
            uri=ffmpeg_plan.output_uri,
            mime_type=qc_policy.required_mime_type,
            duration_ms=ffmpeg_plan.duration_ms,
        ),
        target_id=f"approval-{script.id}",
        policy=qc_policy,
    )
    return ProductionHandoff(
        script=script,
        split=split,
        ass_document=ass_document,
        grok_prompts=grok_prompts,
        video_assets=video_assets,
        voiceover_assets=voiceovers,
        manifest=manifest,
        ffmpeg_plan=ffmpeg_plan,
        final_qc=final_qc,
    )
