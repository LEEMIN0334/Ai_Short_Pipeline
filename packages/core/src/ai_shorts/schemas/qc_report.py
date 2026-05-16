from pydantic import BaseModel, Field


class QCScore(BaseModel):
    name: str
    score: float = Field(ge=0, le=1)
    reason: str


class QCReport(BaseModel):
    target_id: str
    overall_score: float = Field(ge=0, le=1)
    scores: list[QCScore]
    passed: bool
    required_fixes: list[str] = Field(default_factory=list)
