import json

import pytest
from ai_shorts.agents.final_qc import (
    FinalQCPolicy,
    RenderFileQCPolicy,
    evaluate_final_qc,
    evaluate_render_file_qc,
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
                end_ms=3000,
            ),
            CompositionSegment(
                index=1,
                video=MediaRef(uri="assets/video-01.mp4", mime_type="video/mp4"),
                voiceover=MediaRef(uri="assets/voice-01.wav", mime_type="audio/wav"),
                subtitle_ass="assets/subtitles.ass",
                start_ms=3000,
                end_ms=9000,
            ),
        ],
    )


def _rendered_video(duration_ms: int = 9000, mime_type: str = "video/mp4") -> MediaRef:
    return MediaRef(
        uri="build/final.mp4",
        mime_type=mime_type,
        duration_ms=duration_ms,
    )


def test_evaluate_final_qc_passes_complete_render() -> None:
    report = evaluate_final_qc(_manifest(), _rendered_video(), target_id="approval-001")

    assert report.target_id == "approval-001"
    assert report.passed is True
    assert report.overall_score == 1
    assert report.required_fixes == []
    assert [score.name for score in report.scores] == [
        "output_ratio",
        "duration",
        "subtitles",
        "voiceover",
        "media_refs",
    ]


def test_evaluate_final_qc_fails_missing_subtitles_and_voiceover() -> None:
    manifest = _manifest()
    manifest.segments[0].subtitle_ass = None
    manifest.segments[1].voiceover = None

    report = evaluate_final_qc(manifest, _rendered_video())

    assert report.passed is False
    assert "Every segment must include ASS subtitles." in report.required_fixes
    assert "Every segment must include voiceover audio." in report.required_fixes


def test_evaluate_final_qc_fails_bad_ratio_mime_and_duration() -> None:
    manifest = _manifest()
    manifest.output_ratio = "1:1"

    report = evaluate_final_qc(
        manifest,
        _rendered_video(duration_ms=120_000, mime_type="video/quicktime"),
    )

    assert report.passed is False
    assert "Expected output ratio 9:16, got 1:1." in report.required_fixes
    assert any("Rendered duration 120000ms" in fix for fix in report.required_fixes)
    assert any("Rendered mime type must be video/mp4" in fix for fix in report.required_fixes)


def test_evaluate_final_qc_allows_optional_subtitles_and_voiceover() -> None:
    manifest = _manifest()
    manifest.segments[0].subtitle_ass = None
    manifest.segments[0].voiceover = None
    policy = FinalQCPolicy(require_subtitles=False, require_voiceover=False)

    report = evaluate_final_qc(manifest, _rendered_video(), policy=policy)

    assert report.passed is True
    assert report.required_fixes == []


def test_evaluate_final_qc_warns_when_rendered_duration_is_missing() -> None:
    report = evaluate_final_qc(
        _manifest(),
        MediaRef(uri="build/final.mp4", mime_type="video/mp4"),
    )

    assert report.passed is False
    assert "Rendered duration is missing." in report.required_fixes


@pytest.mark.asyncio
async def test_evaluate_render_file_qc_passes_probe_metadata(tmp_path) -> None:
    output = tmp_path / "build/final.mp4"
    output.parent.mkdir(parents=True)
    output.write_bytes(b"mp4")

    async def runner(command: list[str]) -> str:
        assert command[-1] == str(output)
        return json.dumps(
            {
                "format": {"duration": "9.0"},
                "streams": [
                    {"codec_type": "video", "width": 1080, "height": 1920},
                    {"codec_type": "audio"},
                ],
            }
        )

    report = await evaluate_render_file_qc(
        _manifest(),
        _rendered_video(),
        target_id="approval-file-001",
        runner=runner,
        root=tmp_path,
    )

    assert report.target_id == "approval-file-001"
    assert report.passed is True
    assert report.required_fixes == []
    assert [score.name for score in report.scores] == [
        "output_ratio",
        "render_file",
        "probe_duration",
        "probe_resolution",
        "probe_audio",
        "subtitles",
        "voiceover",
        "media_refs",
    ]


@pytest.mark.asyncio
async def test_evaluate_render_file_qc_fails_missing_file_without_probe(tmp_path) -> None:
    called = False

    async def runner(_: list[str]) -> str:
        nonlocal called
        called = True
        return "{}"

    report = await evaluate_render_file_qc(
        _manifest(),
        _rendered_video(),
        runner=runner,
        root=tmp_path,
    )

    assert report.passed is False
    assert called is False
    assert "Rendered file does not exist: build/final.mp4." in report.required_fixes


@pytest.mark.asyncio
async def test_evaluate_render_file_qc_fails_bad_probe_metadata(tmp_path) -> None:
    output = tmp_path / "build/final.mp4"
    output.parent.mkdir(parents=True)
    output.write_bytes(b"mp4")

    async def runner(_: list[str]) -> str:
        return json.dumps(
            {
                "format": {"duration": "12.5"},
                "streams": [
                    {"codec_type": "video", "width": 1920, "height": 1080},
                ],
            }
        )

    report = await evaluate_render_file_qc(
        _manifest(),
        _rendered_video(),
        runner=runner,
        root=tmp_path,
        policy=RenderFileQCPolicy(duration_tolerance_ms=100),
    )

    assert report.passed is False
    assert any("duration drift" in fix for fix in report.required_fixes)
    assert any("Rendered resolution must be 1080x1920" in fix for fix in report.required_fixes)
    assert "ffprobe found no audio stream." in report.required_fixes
