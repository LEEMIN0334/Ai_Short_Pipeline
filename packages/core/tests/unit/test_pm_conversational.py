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
from ai_shorts.cli.telegram_bot import (
    _split_message as _split_bot_message,
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
async def test_pm_queues_trend_task_to_trend_scout(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[AgentTaskCreate] = []

    async def fake_enqueue_task(create: AgentTaskCreate) -> AgentTask:
        created.append(create)
        now = datetime(2026, 5, 16, 12, tzinfo=UTC)
        return AgentTask(
            task_id="task_trend_001",
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

    result = await handle_message("thread_trend_001", "/trend AI video memes")

    assert "Queued task_trend_001 for trend_scout" in result
    assert created[0].agent_id == "trend_scout"
    assert created[0].command == "trend"
    assert created[0].prompt == "AI video memes"


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


@pytest.mark.asyncio
async def test_research_followup_uses_latest_completed_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[AgentTaskCreate] = []
    now = datetime(2026, 5, 16, 12, tzinfo=UTC)
    previous = AgentTask(
        task_id="task_previous_001",
        requested_by="telegram_123456",
        agent_id="research_agent",
        command="research",
        prompt="original web design research",
        status=AgentTaskStatus.SUCCEEDED,
        priority=0,
        result="Previous conclusion\nSource: https://example.com",
        created_at=now,
        updated_at=now,
    )

    async def fake_get_latest_task(*args: object, **kwargs: object) -> AgentTask:
        return previous

    async def fake_enqueue_task(create: AgentTaskCreate) -> AgentTask:
        created.append(create)
        return AgentTask(
            task_id="task_followup_001",
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
        "ai_shorts.agents.pm.conversational.get_latest_task",
        fake_get_latest_task,
    )
    monkeypatch.setattr(
        "ai_shorts.agents.pm.conversational.enqueue_task",
        fake_enqueue_task,
    )

    result = await handle_message("telegram_123456", "/research 2번을 더 자세히 파줘")

    assert "Queued task_followup_001" in result
    assert "Context: continuing from task_previous_001" in result
    assert created[0].metadata["context_task_id"] == "task_previous_001"
    assert created[0].metadata["context_agent_id"] == "research_agent"
    assert "Previous task: task_previous_001" in created[0].prompt
    assert "Follow-up request:" in created[0].prompt


def test_telegram_bot_splits_long_replies_without_truncating() -> None:
    chunks = _split_bot_message("alpha\n\n" + ("detail " * 900), limit=1000)

    assert len(chunks) > 1
    assert all(len(chunk) <= 1000 for chunk in chunks)
    assert chunks[0].startswith("[1/")
    assert chunks[-1].startswith(f"[{len(chunks)}/{len(chunks)}]")


@pytest.mark.asyncio
async def test_developer_followup_uses_latest_developer_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[AgentTaskCreate] = []
    now = datetime(2026, 5, 16, 12, tzinfo=UTC)
    previous = AgentTask(
        task_id="task_dev_previous",
        requested_by="telegram_123456",
        agent_id="developer_agent",
        command="dev",
        prompt="approval dashboard plan",
        status=AgentTaskStatus.SUCCEEDED,
        priority=0,
        result="Developer plan\nFiles: dashboard.py",
        created_at=now,
        updated_at=now,
    )

    async def fake_get_latest_task(*args: object, **kwargs: object) -> AgentTask:
        return previous

    async def fake_enqueue_task(create: AgentTaskCreate) -> AgentTask:
        created.append(create)
        return AgentTask(
            task_id="task_dev_followup",
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
        "ai_shorts.agents.pm.conversational.get_latest_task",
        fake_get_latest_task,
    )
    monkeypatch.setattr(
        "ai_shorts.agents.pm.conversational.enqueue_task",
        fake_enqueue_task,
    )

    result = await handle_message(
        "telegram_123456",
        (
            "/dev \uc774\uc5b4\uc11c \uc2e4\ud589 \uc804 "
            "\ub9ac\uc2a4\ud06c\ub9cc \ub354 \uc815\ub9ac\ud574\uc918"
        ),
    )

    assert "Queued task_dev_followup for developer_agent" in result
    assert created[0].metadata["context_task_id"] == "task_dev_previous"
    assert created[0].metadata["context_agent_id"] == "developer_agent"
    assert "Previous agent: developer_agent" in created[0].prompt


@pytest.mark.asyncio
async def test_plain_followup_uses_latest_completed_agent_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[AgentTaskCreate] = []
    now = datetime(2026, 5, 16, 12, tzinfo=UTC)
    previous = AgentTask(
        task_id="task_script_previous",
        requested_by="telegram_123456",
        agent_id="script_writer",
        command="script",
        prompt="write a hook",
        status=AgentTaskStatus.SUCCEEDED,
        priority=0,
        result="Script preview\nScene 1...",
        created_at=now,
        updated_at=now,
    )

    async def fake_get_latest_task(*args: object, **kwargs: object) -> AgentTask:
        return previous

    async def fake_enqueue_task(create: AgentTaskCreate) -> AgentTask:
        created.append(create)
        return AgentTask(
            task_id="task_plain_followup",
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
        "ai_shorts.agents.pm.conversational.get_latest_task",
        fake_get_latest_task,
    )
    monkeypatch.setattr(
        "ai_shorts.agents.pm.conversational.enqueue_task",
        fake_enqueue_task,
    )

    result = await handle_message(
        "telegram_123456",
        "\uc774\uc5b4\uc11c 2\ubc88\uc744 \ub354 \uc9e7\uac8c \ud574\uc918",
    )

    assert "Queued task_plain_followup for script_writer" in result
    assert created[0].agent_id == "script_writer"
    assert created[0].command == "script"
    assert created[0].metadata["context_task_id"] == "task_script_previous"
