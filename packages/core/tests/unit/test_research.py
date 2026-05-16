from datetime import UTC, datetime

import pytest
from ai_shorts.adapters.chatgpt_deep_research import ChatGPTDeepResearchAdapter
from ai_shorts.adapters.grok_deepsearch import GrokDeepSearchAdapter


@pytest.mark.asyncio
async def test_chatgpt_research_adapter_returns_placeholder_report() -> None:
    report = await ChatGPTDeepResearchAdapter().research("AI shorts trends")

    assert report.id.startswith("chatgpt_")
    assert "AI shorts trends" in report.title
    assert report.created_at.tzinfo == UTC


@pytest.mark.asyncio
async def test_grok_research_adapter_returns_placeholder_report() -> None:
    report = await GrokDeepSearchAdapter().research("creator tools")

    assert report.id.startswith("grok_")
    assert "creator tools" in report.title
    assert report.created_at <= datetime.now(UTC)


@pytest.mark.asyncio
async def test_research_adapters_require_query() -> None:
    with pytest.raises(ValueError):
        await ChatGPTDeepResearchAdapter().research(" ")
