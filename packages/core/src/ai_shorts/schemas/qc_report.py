from enum import StrEnum

from pydantic import BaseModel, Field


class QCRetryStatus(StrEnum):
    APPROVED = "approved"
    RETRY = "retry"
    BLOCKED = "blocked"


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


class QCRetryDecision(BaseModel):
    target_id: str
    status: QCRetryStatus
    approved: bool
    retry_allowed: bool
    attempt_number: int = Field(ge=1)
    max_attempts: int = Field(ge=1)
    overall_score: float = Field(ge=0, le=1)
    next_attempt_number: int | None = None
    required_fixes: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    retry_prompt: str | None = None
