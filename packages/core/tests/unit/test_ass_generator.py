import pytest
from ai_shorts.agents.ass_generator import (
    ASSGeneratorPolicy,
    format_ass_timestamp,
    generate_ass_from_split,
)
from ai_shorts.schemas.script import ScriptSegment, ScriptSplit


def _split() -> ScriptSplit:
    return ScriptSplit(
        script_id="script-01",
        language="ko",
        target_duration_ms=6000,
        segments=[
            ScriptSegment(
                segment_id="segment-01",
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
                segment_id="segment-02",
                script_id="script-01",
                scene_index=0,
                line_index=1,
                chunk_index=0,
                speaker="narrator",
                text="두 번째 장면입니다.",
                start_ms=2500,
                end_ms=6000,
            ),
        ],
    )


def test_generate_ass_from_split_renders_header_style_and_events() -> None:
    document = generate_ass_from_split(_split())

    assert document.script_id == "script-01"
    assert document.event_count == 2
    assert "[Script Info]" in document.content
    assert "PlayResX: 1080" in document.content
    assert "Style: Default,Noto Sans CJK KR,72" in document.content
    assert "Dialogue: 0,0:00:00.00,0:00:02.50,Default,narrator" in document.content
    assert "Dialogue: 0,0:00:02.50,0:00:06.00,Default,narrator" in document.content


def test_generate_ass_from_split_applies_custom_style() -> None:
    document = generate_ass_from_split(
        _split(),
        policy=ASSGeneratorPolicy(
            style_name="ShortsCaption",
            font_name="Pretendard",
            font_size=64,
            margin_v=220,
        ),
    )

    assert "Style: ShortsCaption,Pretendard,64" in document.content
    assert ",220,1" in document.content
    assert "Dialogue: 0,0:00:00.00,0:00:02.50,ShortsCaption,narrator" in document.content


def test_generate_ass_from_split_wraps_and_sanitizes_text() -> None:
    split = _split()
    split.segments[0].text = "This subtitle has {override} text that should wrap cleanly"

    document = generate_ass_from_split(
        split,
        policy=ASSGeneratorPolicy(max_chars_per_line=16),
    )

    assert "{override}" not in document.content
    assert "(override)" in document.content
    assert r"\N" in document.content


def test_generate_ass_from_split_rejects_empty_segments() -> None:
    split = _split()
    split.segments = []

    with pytest.raises(RuntimeError, match="at least one segment"):
        generate_ass_from_split(split)


def test_generate_ass_from_split_rejects_invalid_timing() -> None:
    split = _split()
    split.segments[0].start_ms = 1000
    split.segments[0].end_ms = 1000

    with pytest.raises(RuntimeError, match="end_ms must be greater than start_ms"):
        generate_ass_from_split(split)


def test_format_ass_timestamp_uses_centiseconds() -> None:
    assert format_ass_timestamp(0) == "0:00:00.00"
    assert format_ass_timestamp(3723456) == "1:02:03.45"

    with pytest.raises(RuntimeError, match="must not be negative"):
        format_ass_timestamp(-1)
