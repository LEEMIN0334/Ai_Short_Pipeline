from datetime import UTC, datetime

import pytest
from ai_shorts.adapters.base import CostEvent
from ai_shorts.agents.pm.conversational import handle_message
from ai_shorts.agents.runtime.store import AgentTask, AgentTaskCreate, AgentTaskStatus
from ai_shorts.cli.telegram_bot import (
    TelegramBotRole,
    _queued_task_id,
    _role_routed_text,
    _start_message,
)


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


@pytest.mark.asyncio
async def test_pm_lists_agent_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_URL", "")

    result = await handle_message("thread_agents_001", "/agents")

    assert "pm_supervisor" in result
    assert "/research <topic>" in result


@pytest.mark.asyncio
async def test_pm_queues_research_task(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[AgentTaskCreate] = []

    async def fake_enqueue_task(create: AgentTaskCreate) -> AgentTask:
        created.append(create)
        now = datetime(2026, 5, 16, 12, tzinfo=UTC)
        return AgentTask(
            task_id="task_test_001",
            requested_by=create.requested_by,
            agent_id=create.agent_id,
            command=create.command,
            prompt=create.prompt,
            status=AgentTaskStatus.QUEUED,
            priority=create.priority,
            result="",
            created_at=now,
            updated_at=now,
        )

    monkeypatch.setattr(
        "ai_shorts.agents.pm.conversational.enqueue_task",
        fake_enqueue_task,
    )

    result = await handle_message("thread_research_001", "/research AI shorts workflow")

    assert "Queued task_test_001 for research_agent" in result
    assert created[0].requested_by == "thread_research_001"
    assert created[0].agent_id == "research_agent"
    assert created[0].prompt == "AI shorts workflow"


@pytest.mark.asyncio
async def test_pm_queues_developer_task(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[AgentTaskCreate] = []

    async def fake_enqueue_task(create: AgentTaskCreate) -> AgentTask:
        created.append(create)
        now = datetime(2026, 5, 16, 12, tzinfo=UTC)
        return AgentTask(
            task_id="task_dev_001",
            requested_by=create.requested_by,
            agent_id=create.agent_id,
            command=create.command,
            prompt=create.prompt,
            status=AgentTaskStatus.QUEUED,
            priority=create.priority,
            result="",
            metadata=create.metadata,
            created_at=now,
            updated_at=now,
        )

    monkeypatch.setattr(
        "ai_shorts.agents.pm.conversational.enqueue_task",
        fake_enqueue_task,
    )

    result = await handle_message("telegram_123456", "/dev add approval dashboard")

    assert "Queued task_dev_001 for developer_agent" in result
    assert created[0].command == "dev"
    assert created[0].prompt == "add approval dashboard"


@pytest.mark.asyncio
async def test_pm_attaches_telegram_chat_id_to_agent_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[AgentTaskCreate] = []

    async def fake_enqueue_task(create: AgentTaskCreate) -> AgentTask:
        created.append(create)
        now = datetime(2026, 5, 16, 12, tzinfo=UTC)
        return AgentTask(
            task_id="task_telegram_001",
            requested_by=create.requested_by,
            agent_id=create.agent_id,
            command=create.command,
            prompt=create.prompt,
            status=AgentTaskStatus.QUEUED,
            priority=create.priority,
            result="",
            metadata=create.metadata,
            created_at=now,
            updated_at=now,
        )

    monkeypatch.setattr(
        "ai_shorts.agents.pm.conversational.enqueue_task",
        fake_enqueue_task,
    )

    result = await handle_message("telegram_123456", "/mvp setup check")

    assert "Queued task_telegram_001" in result
    assert created[0].metadata == {
        "channel": "telegram",
        "telegram_chat_id": "123456",
    }


def test_telegram_bot_detects_queued_task_id() -> None:
    reply = (
        "Queued task_abc123def456 for pm_supervisor.\n"
        "The always-on agent worker will post progress updates here.\n"
        "Check status with: /task task_abc123def456"
    )

    assert _queued_task_id(reply) == "task_abc123def456"
    assert _queued_task_id("hello") is None


def test_role_specific_telegram_bots_route_plain_text() -> None:
    assert (
        _role_routed_text(TelegramBotRole.RESEARCH, "compare video APIs")
        == "/research compare video APIs"
    )
    assert (
        _role_routed_text(TelegramBotRole.DEVELOPER, "add approval dashboard")
        == "/dev add approval dashboard"
    )
    assert _role_routed_text(TelegramBotRole.PM, "hello") == "hello"
    assert _role_routed_text(TelegramBotRole.DEVELOPER, "/task task_123") == "/task task_123"


def test_telegram_start_message_does_not_queue_agent_work() -> None:
    message = _start_message(TelegramBotRole.RESEARCH, 123456)

    assert "AI Shorts Research Bot connected" in message
    assert "chat_id=123456" in message
