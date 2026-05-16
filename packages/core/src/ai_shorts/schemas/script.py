from pydantic import BaseModel, Field


class ScriptLine(BaseModel):
    speaker: str
    text: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    emphasis_cue: str | None = None


class ScriptScene(BaseModel):
    index: int = Field(ge=0)
    visual_prompt: str
    lines: list[ScriptLine]


class Script(BaseModel):
    id: str
    template_id: str
    title: str
    target_duration_ms: int = Field(gt=0)
    scenes: list[ScriptScene]
    language: str = "ko"


class ScriptSegment(BaseModel):
    segment_id: str
    script_id: str
    scene_index: int = Field(ge=0)
    line_index: int = Field(ge=0)
    chunk_index: int = Field(ge=0)
    speaker: str
    text: str = Field(min_length=1)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    emphasis_cue: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class ScriptSplit(BaseModel):
    script_id: str
    language: str = "ko"
    target_duration_ms: int = Field(gt=0)
    segments: list[ScriptSegment]
