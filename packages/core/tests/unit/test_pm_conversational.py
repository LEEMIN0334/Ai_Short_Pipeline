import pytest

from ai_shorts.agents.pm.conversational import handle_message


@pytest.mark.asyncio
async def test_pm_echoes_non_ping(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_URL", "")

    result = await handle_message("thread_001", "hello")

    assert result == "echo: hello"
