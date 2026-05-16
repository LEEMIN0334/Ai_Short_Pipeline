from pydantic import BaseModel, Field


class MediaRef(BaseModel):
    uri: str
    mime_type: str
    duration_ms: int | None = Field(default=None, gt=0)


class CompositionSegment(BaseModel):
    index: int = Field(ge=0)
    video: MediaRef
    voiceover: MediaRef | None = None
    subtitle_ass: str | None = None
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)


class CompositionManifest(BaseModel):
    script_id: str
    output_ratio: str = "9:16"
    fps: int = Field(default=30, gt=0)
    segments: list[CompositionSegment]
    bgm: MediaRef | None = None
