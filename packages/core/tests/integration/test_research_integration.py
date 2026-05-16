from datetime import UTC, datetime

import pytest
from ai_shorts.agents.research import ResearchAgent, search_research_reports
from ai_shorts.config import get_settings
from ai_shorts.schemas.research_report import ResearchReport, ResearchSource
from ai_shorts.storage.local import LocalStorage
from ai_shorts.storage.postgres import get_conn


class FixtureResearchProvider:
    async def research(self, query: str) -> ResearchReport:
        return ResearchReport(
            id="fixture_research_001",
            title=f"Fixture report for {query}",
            summary="Collection schema validation and creator trend research.",
            body_markdown="# Fixture\n\nCollection schema validation for creator trends.",
            sources=[
                ResearchSource(
                    title="Example",
                    url="https://example.com",
                    summary="Fixture source",
                )
            ],
            created_at=datetime.now(UTC),
        )


@pytest.mark.asyncio
async def test_research_agent_stores_and_searches_report(tmp_path) -> None:  # type: ignore[no-untyped-def]
    if not get_settings().postgres_url:
        pytest.skip("POSTGRES_URL is not configured")

    title_prefix = "Fixture report for phase1 research"
    storage = LocalStorage(root=tmp_path)
    agent = ResearchAgent(provider=FixtureResearchProvider(), storage=storage)

    try:
        report = await agent.run_and_store("phase1 research")

        assert await storage.exists("research/fixture_research_001.md")
        rows = await search_research_reports("creator trends")

        assert report.title == title_prefix
        assert any(row["title"] == title_prefix for row in rows)
    finally:
        async with get_conn() as conn:
            await conn.execute("DELETE FROM research_report WHERE title = $1", title_prefix)
