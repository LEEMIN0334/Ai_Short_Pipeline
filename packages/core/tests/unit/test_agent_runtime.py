import asyncio
from datetime import UTC, datetime
from pathlib import Path
from sys import executable

import pytest
from ai_shorts.agents.runtime.developer_execution import (
    is_developer_execution_request,
    run_developer_execution,
    strip_developer_execution_prefix,
)
from ai_shorts.agents.runtime.handlers import execute_agent_task
from ai_shorts.agents.runtime.registry import render_agent_catalog
from ai_shorts.agents.runtime.research_execution import run_web_research
from ai_shorts.agents.runtime.store import AgentTask, AgentTaskStatus
from ai_shorts.agents.runtime.telegram_notify import _telegram_token_for_task, summarize_task_result


def _task(agent_id: str, prompt: str, command: str = "preview") -> AgentTask:
    now = datetime(2026, 5, 16, 12, tzinfo=UTC)
    return AgentTask(
        task_id=f"task_{agent_id}",
        requested_by="test",
        agent_id=agent_id,
        command=command,
        prompt=prompt,
        status=AgentTaskStatus.RUNNING,
        priority=0,
        result="",
        created_at=now,
        updated_at=now,
    )


def _telegram_task(agent_id: str, prompt: str) -> AgentTask:
    return _task(agent_id, prompt).model_copy(
        update={
            "requested_by": "telegram_123456",
            "metadata": {
                "channel": "telegram",
                "telegram_chat_id": "123456",
                "telegram_status_message_id": 77,
                "telegram_progress_mode": "edit",
            },
        }
    )


def test_agent_catalog_lists_command_surface() -> None:
    catalog = render_agent_catalog()

    assert "pm_supervisor" in catalog
    assert "developer_agent" in catalog
    assert "/research <topic>" in catalog
    assert "/dev <feature>" in catalog
    assert "/mvp <topic>" in catalog


@pytest.mark.asyncio
async def test_research_agent_runs_web_research(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_web_research(prompt: str, **kwargs: object) -> str:
        return (
            f"Web research: {prompt}\n"
            "Execution status: succeeded\n"
            "Exit code: 0\n\n"
            "핵심 결론: 웹 리서치 완료\n출처: https://example.com"
        )

    monkeypatch.setattr(
        "ai_shorts.agents.runtime.handlers.run_web_research",
        fake_web_research,
    )

    result = await execute_agent_task(_task("research_agent", "AI shorts workflow"))

    assert "Web research: AI shorts workflow" in result
    assert "핵심 결론" in result
    assert "Instagram" not in result


@pytest.mark.asyncio
async def test_trend_scout_preview_owns_platform_signals() -> None:
    result = await execute_agent_task(_task("trend_scout", "AI shorts workflow"))

    assert "Trend Scout preview: AI shorts workflow" in result
    assert "Selected trend signals:" in result
    assert "instagram" in result.lower()


@pytest.mark.asyncio
async def test_research_agent_can_introduce_itself() -> None:
    messages: list[str] = []

    async def progress(message: str) -> None:
        messages.append(message)

    result = await execute_agent_task(_task("research_agent", "자기소개 해줘"), progress=progress)

    assert result.startswith("Research Agent intro:")
    assert any("[1/3]" in message for message in messages)


@pytest.mark.asyncio
async def test_script_writer_preview_runs_without_external_services() -> None:
    result = await execute_agent_task(_task("script_writer", "AI shorts workflow"))

    assert "Script preview:" in result
    assert "Script Writer -> Splitter" in result
    assert "TTS/subtitle segments:" in result


@pytest.mark.asyncio
async def test_pm_supervisor_mvp_preview_runs_without_external_services() -> None:
    result = await execute_agent_task(_task("pm_supervisor", "AI shorts workflow"))

    assert "MVP preview: AI shorts workflow" in result
    assert "Final QC: pass" in result
    assert "No paid external API was called" in result


@pytest.mark.asyncio
async def test_developer_agent_preview_requires_research_and_pm_gate() -> None:
    result = await execute_agent_task(_task("developer_agent", "add approval dashboard"))

    assert "Developer plan: add approval dashboard" in result
    assert "Research Agent -> PM Supervisor -> Developer Agent" in result
    assert "waits for research direction and PM approval" in result
    assert "Developer self-review gate:" in result
    assert "If self-review fails" in result
    assert "No code was changed" in result


def test_developer_execution_request_requires_explicit_approval() -> None:
    assert is_developer_execution_request("실행 승인: dashboard button")
    assert is_developer_execution_request("/dev execute dashboard button")
    assert not is_developer_execution_request("dashboard button 계획해줘")
    assert strip_developer_execution_prefix("실행 승인: dashboard button") == "dashboard button"


@pytest.mark.asyncio
async def test_developer_execution_uses_codex_runner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    async def fake_runner(
        command: list[str],
        cwd: Path,
        output_path: str,
        timeout_seconds: int,
    ) -> tuple[int, str, str]:
        captured["command"] = command
        captured["cwd"] = cwd
        captured["timeout_seconds"] = timeout_seconds
        await asyncio.to_thread(
            Path(output_path).write_text,
            "변경 파일: 없음\n검증: fake passed",
            encoding="utf-8",
        )
        return 0, "", ""

    monkeypatch.setenv("AI_SHORTS_STUDIO_ROOT", str(tmp_path))
    monkeypatch.setenv("OPENCLAW_CODEX_APP_SERVER_BIN", executable)

    result = await run_developer_execution(
        "실행 승인: fake approved change",
        runner=fake_runner,
    )

    command = captured["command"]
    assert isinstance(command, list)
    assert "exec" in command
    assert "workspace-write" in command
    assert str(captured["cwd"]) == str(tmp_path)
    assert "Execution status: succeeded" in result
    assert "변경 파일" in result


@pytest.mark.asyncio
async def test_web_research_uses_codex_search_runner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    async def fake_runner(
        command: list[str],
        cwd: Path,
        output_path: str,
        timeout_seconds: int,
    ) -> tuple[int, str, str]:
        captured["command"] = command
        captured["cwd"] = cwd
        captured["timeout_seconds"] = timeout_seconds
        await asyncio.to_thread(
            Path(output_path).write_text,
            "핵심 결론: fake web research\n출처: https://example.com",
            encoding="utf-8",
        )
        return 0, "", ""

    monkeypatch.setenv("AI_SHORTS_STUDIO_ROOT", str(tmp_path))
    monkeypatch.setenv("OPENCLAW_CODEX_APP_SERVER_BIN", executable)

    result = await run_web_research("AI video platform pricing", runner=fake_runner)

    command = captured["command"]
    assert isinstance(command, list)
    assert "exec" in command
    assert "--search" in command
    assert "read-only" in command
    assert 'model_reasoning_effort="xhigh"' in command
    assert str(captured["cwd"]) == str(tmp_path)
    assert "Execution status: succeeded" in result
    assert "fake web research" in result


@pytest.mark.asyncio
async def test_agent_task_emits_progress_stages() -> None:
    messages: list[str] = []

    async def progress(message: str) -> None:
        messages.append(message)

    await execute_agent_task(_task("pm_supervisor", "AI shorts workflow"), progress=progress)

    assert messages[0].startswith("[1/5]")
    assert any("Script Writer" in message for message in messages)
    assert any("QC Agent" in message for message in messages)


def test_task_result_summary_is_concise() -> None:
    task = _task("pm_supervisor", "AI shorts workflow")
    result = "MVP preview\nFinal QC: pass (1.0)\nRetry decision: approved"

    summary = summarize_task_result(task, result)

    assert "Conclusion: local MVP gate passed" in summary
    assert f"Details: /task {task.task_id}" in summary
    assert "Final QC: pass (1.0)" not in summary


def test_developer_task_result_summary_is_concise() -> None:
    task = _task("developer_agent", "add approval dashboard")

    summary = summarize_task_result(task, "Developer plan: add approval dashboard")

    assert "developer plan and self-review gate are ready" in summary
    assert f"Details: /task {task.task_id}" in summary


def test_developer_execution_summary_includes_result_body() -> None:
    task = _task("developer_agent", "실행 승인: fake change")
    result = (
        "Developer execution: fake change\n"
        "Execution status: succeeded\n"
        "Exit code: 0\n\n"
        "변경 파일: tests/example.py\n검증: passed"
    )

    summary = summarize_task_result(task, result)

    assert summary.startswith(f"완료: {task.task_id}")
    assert "변경 파일: tests/example.py" in summary
    assert f"자세히 보기: /task {task.task_id}" in summary


def test_web_research_summary_includes_result_body() -> None:
    task = _task("research_agent", "AI video platform pricing")
    result = (
        "Web research: AI video platform pricing\n"
        "Execution status: succeeded\n"
        "Exit code: 0\n\n"
        "핵심 결론: 웹 리서치 완료\n출처: https://example.com"
    )

    summary = summarize_task_result(task, result)

    assert summary.startswith(f"완료: {task.task_id}")
    assert "핵심 결론: 웹 리서치 완료" in summary
    assert f"자세히 보기: /task {task.task_id}" in summary


def test_intro_task_result_summary_is_concise() -> None:
    task = _task("research_agent", "자기소개 해줘")

    summary = summarize_task_result(
        task,
        "Research Agent intro:\n나는 AI Shorts Pipeline의 리서치 담당 하위 agent입니다.",
    )

    assert summary.startswith(f"완료: {task.task_id}")
    assert "리서치 담당 하위 agent" in summary
    assert f"자세히 보기: /task {task.task_id}" in summary


def test_telegram_task_keeps_edit_message_metadata() -> None:
    task = _telegram_task("grok_planner", "AI shorts workflow")

    assert task.metadata["telegram_chat_id"] == "123456"
    assert task.metadata["telegram_status_message_id"] == 77
    assert task.metadata["telegram_progress_mode"] == "edit"


def test_telegram_notification_uses_role_specific_bot_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "pm-token")
    monkeypatch.setenv("TELEGRAM_RESEARCH_BOT_TOKEN", "research-token")
    monkeypatch.setenv("TELEGRAM_DEVELOPER_BOT_TOKEN", "developer-token")

    assert _telegram_token_for_task(_telegram_task("research_agent", "topic")) == "pm-token"
    research_metadata = {
        **_telegram_task("research_agent", "topic").metadata,
        "telegram_bot_role": "research",
    }
    developer_metadata = {
        **_telegram_task("developer_agent", "topic").metadata,
        "telegram_bot_role": "developer",
    }
    research_task = _telegram_task("research_agent", "topic").model_copy(
        update={"metadata": research_metadata}
    )
    developer_task = _telegram_task("developer_agent", "topic").model_copy(
        update={"metadata": developer_metadata}
    )

    assert _telegram_token_for_task(research_task) == "research-token"
    assert _telegram_token_for_task(developer_task) == "developer-token"
