from pydantic import BaseModel, Field

from ai_shorts.schemas.script import ScriptSegment, ScriptSplit


class ASSGeneratorPolicy(BaseModel):
    """Subtitle styling and layout defaults for vertical short-form videos."""

    style_name: str = "Default"
    font_name: str = "Noto Sans CJK KR"
    font_size: int = Field(default=72, gt=0)
    play_res_x: int = Field(default=1080, gt=0)
    play_res_y: int = Field(default=1920, gt=0)
    alignment: int = Field(default=2, ge=1, le=9)
    margin_l: int = Field(default=80, ge=0)
    margin_r: int = Field(default=80, ge=0)
    margin_v: int = Field(default=180, ge=0)
    max_chars_per_line: int = Field(default=18, ge=8)
    primary_colour: str = "&H00FFFFFF"
    secondary_colour: str = "&H000000FF"
    outline_colour: str = "&H00000000"
    back_colour: str = "&H96000000"
    outline: int = Field(default=4, ge=0)
    shadow: int = Field(default=0, ge=0)


class ASSDocument(BaseModel):
    script_id: str
    content: str
    event_count: int = Field(ge=0)


def generate_ass_from_split(
    script_split: ScriptSplit,
    *,
    policy: ASSGeneratorPolicy | None = None,
) -> ASSDocument:
    """Render an ASS subtitle document from timed script segments."""

    active_policy = policy or ASSGeneratorPolicy()
    if not script_split.segments:
        raise RuntimeError("Script split must contain at least one segment")

    event_lines = [_dialogue_line(segment, active_policy) for segment in script_split.segments]
    content = "\n".join(
        [
            *_script_info(script_split, active_policy),
            "",
            *_styles(active_policy),
            "",
            *_events(event_lines),
        ]
    )
    return ASSDocument(
        script_id=script_split.script_id,
        content=content,
        event_count=len(event_lines),
    )


def format_ass_timestamp(ms: int) -> str:
    """Convert milliseconds to the h:mm:ss.cc timestamp used by ASS events."""

    if ms < 0:
        raise RuntimeError("ASS timestamp must not be negative")

    centiseconds = ms // 10
    hours = centiseconds // 360_000
    minutes = (centiseconds % 360_000) // 6_000
    seconds = (centiseconds % 6_000) // 100
    remainder = centiseconds % 100
    return f"{hours}:{minutes:02d}:{seconds:02d}.{remainder:02d}"


def _script_info(script_split: ScriptSplit, policy: ASSGeneratorPolicy) -> list[str]:
    return [
        "[Script Info]",
        f"Title: {script_split.script_id}",
        "ScriptType: v4.00+",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "YCbCr Matrix: TV.709",
        f"PlayResX: {policy.play_res_x}",
        f"PlayResY: {policy.play_res_y}",
    ]


def _styles(policy: ASSGeneratorPolicy) -> list[str]:
    return [
        "[V4+ Styles]",
        (
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
            "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
            "MarginL, MarginR, MarginV, Encoding"
        ),
        (
            f"Style: {policy.style_name},{policy.font_name},{policy.font_size},"
            f"{policy.primary_colour},{policy.secondary_colour},{policy.outline_colour},"
            f"{policy.back_colour},0,0,0,0,100,100,0,0,1,{policy.outline},"
            f"{policy.shadow},{policy.alignment},{policy.margin_l},{policy.margin_r},"
            f"{policy.margin_v},1"
        ),
    ]


def _events(event_lines: list[str]) -> list[str]:
    return [
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        *event_lines,
    ]


def _dialogue_line(segment: ScriptSegment, policy: ASSGeneratorPolicy) -> str:
    if segment.end_ms <= segment.start_ms:
        raise RuntimeError("ASS dialogue end_ms must be greater than start_ms")

    return (
        "Dialogue: 0,"
        f"{format_ass_timestamp(segment.start_ms)},"
        f"{format_ass_timestamp(segment.end_ms)},"
        f"{policy.style_name},{segment.speaker},0000,0000,0000,,"
        f"{_ass_text(segment.text, policy.max_chars_per_line)}"
    )


def _ass_text(text: str, max_chars_per_line: int) -> str:
    sanitized = text.replace("{", "(").replace("}", ")")
    lines: list[str] = []
    for paragraph in sanitized.splitlines():
        normalized = " ".join(paragraph.split())
        if normalized:
            lines.extend(_wrap_text(normalized, max_chars_per_line))

    if not lines:
        raise RuntimeError("ASS dialogue text must not be empty")
    return r"\N".join(lines)


def _wrap_text(text: str, max_chars_per_line: int) -> list[str]:
    if len(text) <= max_chars_per_line:
        return [text]

    wrapped: list[str] = []
    current = ""
    for token in text.split(" "):
        candidate = f"{current} {token}".strip()
        if len(candidate) <= max_chars_per_line:
            current = candidate
            continue
        if current:
            wrapped.append(current)
        wrapped.extend(_hard_wrap_token(token, max_chars_per_line))
        current = ""

    if current:
        wrapped.append(current)
    return _merge_wrapped_lines(wrapped, max_chars_per_line)


def _hard_wrap_token(token: str, max_chars_per_line: int) -> list[str]:
    if len(token) <= max_chars_per_line:
        return [token]
    return [
        token[index : index + max_chars_per_line]
        for index in range(0, len(token), max_chars_per_line)
    ]


def _merge_wrapped_lines(lines: list[str], max_chars_per_line: int) -> list[str]:
    merged: list[str] = []
    for line in lines:
        if not merged:
            merged.append(line)
            continue

        candidate = f"{merged[-1]} {line}".strip()
        if len(candidate) <= max_chars_per_line:
            merged[-1] = candidate
        else:
            merged.append(line)
    return merged
