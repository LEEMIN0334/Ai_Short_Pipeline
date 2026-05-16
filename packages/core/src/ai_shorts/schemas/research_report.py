from datetime import datetime

from pydantic import BaseModel, Field


class ResearchSource(BaseModel):
    title: str
    url: str
    summary: str = ""


class ResearchReport(BaseModel):
    id: str
    title: str
    summary: str
    body_markdown: str
    sources: list[ResearchSource] = Field(default_factory=list)
    created_at: datetime
