from typing import Protocol

from ai_shorts.schemas.research_report import ResearchReport


class ResearchProvider(Protocol):
    async def research(self, query: str) -> ResearchReport:
        """Run deep research and return a normalized report."""
