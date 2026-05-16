import re
from itertools import pairwise

from pydantic import BaseModel, Field

from ai_shorts.schemas.script import Script, ScriptLine, ScriptSegment, ScriptSplit


class SplitterPolicy(BaseModel):
    """Rules for splitting scripts into TTS and subtitle-safe segments."""

    segment_id_prefix: str = "segment"
    max_segment_chars: int = Field(default=120, ge=20, le=2000)


def split_script(script: Script, *, policy: SplitterPolicy | None = None) -> ScriptSplit:
    """Split a script into deterministic segments for TTS, subtitles, and composition."""

    active_policy = policy or SplitterPolicy()
    segments: list[ScriptSegment] = []

    for scene in script.scenes:
        for line_index, line in enumerate(scene.lines):
            chunks = _split_line_text(line.text, active_policy.max_segment_chars)
            boundaries = _allocate_timing(line, chunks)
            for chunk_index, (chunk, (start_ms, end_ms)) in enumerate(
                zip(chunks, boundaries, strict=True)
            ):
                segments.append(
                    ScriptSegment(
                        segment_id=_segment_id(
                            active_policy,
                            script.id,
                            scene.index,
                            line_index,
                            chunk_index,
                        ),
                        script_id=script.id,
                        scene_index=scene.index,
                        line_index=line_index,
                        chunk_index=chunk_index,
                        speaker=line.speaker,
                        text=chunk,
                        start_ms=start_ms,
                        end_ms=end_ms,
                        emphasis_cue=line.emphasis_cue,
                        metadata={
                            "scene_visual_prompt": scene.visual_prompt,
                            "source_line_start_ms": line.start_ms,
                            "source_line_end_ms": line.end_ms,
                            "chunk_count": len(chunks),
                        },
                    )
                )

    return ScriptSplit(
        script_id=script.id,
        language=script.language,
        target_duration_ms=script.target_duration_ms,
        segments=segments,
    )


def _split_line_text(text: str, max_chars: int) -> list[str]:
    normalized = " ".join(text.split())
    if not normalized:
        raise RuntimeError("Script line text must not be empty")
    if len(normalized) <= max_chars:
        return [normalized]

    chunks: list[str] = []
    current = ""
    for token in normalized.split(" "):
        candidate = f"{current} {token}".strip()
        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            chunks.append(current)
        chunks.extend(_hard_wrap_token(token, max_chars))
        current = ""

    if current:
        chunks.append(current)

    return _merge_small_chunks(chunks, max_chars)


def _hard_wrap_token(token: str, max_chars: int) -> list[str]:
    if len(token) <= max_chars:
        return [token]
    return [token[index : index + max_chars] for index in range(0, len(token), max_chars)]


def _merge_small_chunks(chunks: list[str], max_chars: int) -> list[str]:
    merged: list[str] = []
    for chunk in chunks:
        if not merged:
            merged.append(chunk)
            continue

        candidate = f"{merged[-1]} {chunk}".strip()
        if len(candidate) <= max_chars:
            merged[-1] = candidate
        else:
            merged.append(chunk)
    return merged


def _allocate_timing(line: ScriptLine, chunks: list[str]) -> list[tuple[int, int]]:
    if line.end_ms <= line.start_ms:
        raise RuntimeError("Script line end_ms must be greater than start_ms")

    if len(chunks) == 1:
        return [(line.start_ms, line.end_ms)]

    duration_ms = line.end_ms - line.start_ms
    if duration_ms < len(chunks):
        raise RuntimeError("Script line duration is too short for the requested split")

    chunk_lengths = [max(len(chunk), 1) for chunk in chunks]
    total_chars = sum(chunk_lengths)
    boundaries = [line.start_ms]
    consumed_chars = 0

    for index, chunk_length in enumerate(chunk_lengths[:-1]):
        consumed_chars += chunk_length
        raw_end_ms = line.start_ms + round(duration_ms * consumed_chars / total_chars)
        remaining_chunks = len(chunks) - index - 1
        min_end_ms = boundaries[-1] + 1
        max_end_ms = line.end_ms - remaining_chunks
        boundaries.append(min(max(raw_end_ms, min_end_ms), max_end_ms))

    boundaries.append(line.end_ms)
    return list(pairwise(boundaries))


def _segment_id(
    policy: SplitterPolicy,
    script_id: str,
    scene_index: int,
    line_index: int,
    chunk_index: int,
) -> str:
    safe_script_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", script_id).strip("-") or "script"
    return (
        f"{policy.segment_id_prefix}-{safe_script_id}"
        f"-s{scene_index:02d}-l{line_index:02d}-c{chunk_index:02d}"
    )
