import pytest
from ai_shorts.adapters.base import CostEvent
from ai_shorts.agents.pm.conversational import handle_message


@pytest.mark.asyncio
async def test_pm_echoes_non_ping(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_URL", "")

    result = await handle_message("thread_001", "hello")

    assert result == "echo: hello"


@pytest.mark.asyncio
async def test_pm_handles_ping_with_stub_cost_sink(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[tuple[str, str, CostEvent]] = []

    def fake_make_sink(job_id: str, agent_id: str):
        async def sink(event: CostEvent) -> None:
            events.append((job_id, agent_id, event))

        return sink

    monkeypatch.setattr(
        "ai_shorts.agents.pm.conversational.make_postgres_sink",
        fake_make_sink,
    )

    result = await handle_message("thread_ping_001", "ping")

    assert result == "pong (via stub-output:ping)"
    assert len(events) == 1
    job_id, agent_id, event = events[0]
    assert job_id == "thread_ping_001"
    assert agent_id == "pm"
    assert event.service == "stub"
    assert event.operation == "do_thing"
