from itertools import pairwise

import pytest
from ai_shorts.agents.splitter import SplitterPolicy, split_script
from ai_shorts.schemas.script import Script, ScriptLine, ScriptScene


def _script(line_text: str = "첫 장면의 핵심을 짧게 설명합니다.") -> Script:
    return Script(
        id="script-01",
        template_id="benchmark-01",
        title="Splitter Test",
        target_duration_ms=10000,
        scenes=[
            ScriptScene(
                index=0,
                visual_prompt="Open on the final result.",
                lines=[
                    ScriptLine(
                        speaker="narrator",
                        text=line_text,
                        start_ms=0,
                        end_ms=4000,
                        emphasis_cue="hook",
                    )
                ],
            ),
            ScriptScene(
                index=1,
                visual_prompt="Show the proof.",
                lines=[
                    ScriptLine(
                        speaker="narrator",
                        text="두 번째 장면입니다.",
                        start_ms=4000,
                        end_ms=10000,
                    )
                ],
            ),
        ],
    )


def test_split_script_preserves_scene_line_timing_and_metadata() -> None:
    split = split_script(_script())

    assert split.script_id == "script-01"
    assert split.language == "ko"
    assert split.target_duration_ms == 10000
    assert [segment.segment_id for segment in split.segments] == [
        "segment-script-01-s00-l00-c00",
        "segment-script-01-s01-l00-c00",
    ]
    assert [(segment.start_ms, segment.end_ms) for segment in split.segments] == [
        (0, 4000),
        (4000, 10000),
    ]
    assert split.segments[0].scene_index == 0
    assert split.segments[0].line_index == 0
    assert split.segments[0].chunk_index == 0
    assert split.segments[0].emphasis_cue == "hook"
    assert split.segments[0].metadata["scene_visual_prompt"] == "Open on the final result."


def test_split_script_chunks_long_lines_and_distributes_timing() -> None:
    split = split_script(
        _script(" ".join(["repeatable"] * 10)),
        policy=SplitterPolicy(max_segment_chars=32),
    )
    first_scene_segments = [
        segment for segment in split.segments if segment.scene_index == 0
    ]

    assert len(first_scene_segments) == 4
    assert all(len(segment.text) <= 32 for segment in first_scene_segments)
    assert first_scene_segments[0].start_ms == 0
    assert first_scene_segments[-1].end_ms == 4000
    assert all(
        previous.end_ms == current.start_ms
        for previous, current in pairwise(first_scene_segments)
    )
    assert all(segment.end_ms > segment.start_ms for segment in first_scene_segments)
    assert [segment.chunk_index for segment in first_scene_segments] == [0, 1, 2, 3]


def test_split_script_hard_wraps_single_tokens() -> None:
    split = split_script(
        _script("a" * 75),
        policy=SplitterPolicy(max_segment_chars=30),
    )

    first_scene_segments = [
        segment for segment in split.segments if segment.scene_index == 0
    ]
    assert [len(segment.text) for segment in first_scene_segments] == [30, 30, 15]


def test_split_script_rejects_blank_line_text() -> None:
    with pytest.raises(RuntimeError, match="Script line text must not be empty"):
        split_script(_script("   "))


def test_split_script_rejects_invalid_line_timing() -> None:
    script = _script()
    script.scenes[0].lines[0].start_ms = 1000
    script.scenes[0].lines[0].end_ms = 1000

    with pytest.raises(RuntimeError, match="end_ms must be greater than start_ms"):
        split_script(script)
