from pydantic import BaseModel, Field, HttpUrl


class BenchmarkScene(BaseModel):
    index: int = Field(ge=0)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    visual_summary: str
    hook: str | None = None
    camera_motion: str | None = None
    on_screen_text: str | None = None


class BenchmarkTemplate(BaseModel):
    id: str
    source_url: HttpUrl
    title: str
    category: str
    duration_ms: int = Field(gt=0)
    scenes: list[BenchmarkScene]
    copy_button_text: str
    notes: str = ""
