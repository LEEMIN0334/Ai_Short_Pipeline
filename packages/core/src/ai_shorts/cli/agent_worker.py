import argparse
import asyncio
from collections.abc import Sequence

from ai_shorts.agents.runtime.handlers import execute_agent_task
from ai_shorts.agents.runtime.registry import AGENT_DEFINITIONS
from ai_shorts.agents.runtime.store import (
    AgentRuntimeStatus,
    AgentTask,
    claim_next_task,
    mark_agent_heartbeat,
    mark_task_failed,
    mark_task_succeeded,
    register_agents,
)
from ai_shorts.agents.runtime.telegram_notify import (
    notify_task_progress,
    summarize_task_error,
    summarize_task_result,
)

PROGRESS_DELAY_SECONDS = 1.2


async def run_worker(
    *,
    agent_ids: Sequence[str] | None = None,
    once: bool = False,
    poll_seconds: float = 2.0,
) -> None:
    active_agent_ids = list(agent_ids or [definition.agent_id for definition in AGENT_DEFINITIONS])
    await _register_agents_with_retry(once=once, poll_seconds=poll_seconds)
    await _heartbeat_all(active_agent_ids, AgentRuntimeStatus.IDLE)

    while True:
        try:
            task = await claim_next_task(active_agent_ids)
        except Exception as exc:
            print(f"agent-worker waiting for task store: {type(exc).__name__}: {exc}")
            if once:
                raise
            await asyncio.sleep(poll_seconds)
            continue

        if task is None:
            await _heartbeat_all(active_agent_ids, AgentRuntimeStatus.IDLE)
            if once:
                return
            await asyncio.sleep(poll_seconds)
            continue

        await mark_agent_heartbeat(task.agent_id, AgentRuntimeStatus.RUNNING)
        await _notify_task(
            task,
            _running_status_message(
                task,
                "시작 준비 중: 큐에서 작업을 가져왔고 담당 agent를 깨우는 중입니다.",
            ),
        )

        async def progress(message: str, current_task: AgentTask = task) -> None:
            await _notify_task(current_task, _running_status_message(current_task, message))

        try:
            result = await execute_agent_task(
                task,
                progress=progress,
                progress_delay_seconds=PROGRESS_DELAY_SECONDS,
            )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            failed_task = await mark_task_failed(task.task_id, error)
            await mark_agent_heartbeat(task.agent_id, AgentRuntimeStatus.ERROR)
            await _notify_task(failed_task, summarize_task_error(failed_task, error))
        else:
            finished_task = await mark_task_succeeded(task.task_id, result)
            await mark_agent_heartbeat(task.agent_id, AgentRuntimeStatus.IDLE)
            await _notify_task(finished_task, summarize_task_result(finished_task, result))


async def _register_agents_with_retry(*, once: bool, poll_seconds: float) -> None:
    while True:
        try:
            await register_agents(AGENT_DEFINITIONS)
        except Exception as exc:
            print(f"agent-worker waiting for agent registry: {type(exc).__name__}: {exc}")
            if once:
                raise
            await asyncio.sleep(poll_seconds)
            continue
        return


async def _heartbeat_all(
    agent_ids: Sequence[str],
    status: AgentRuntimeStatus,
) -> None:
    for agent_id in agent_ids:
        try:
            await mark_agent_heartbeat(agent_id, status)
        except Exception as exc:
            print(f"agent-worker heartbeat skipped for {agent_id}: {type(exc).__name__}: {exc}")


async def _notify_task(task: AgentTask, message: str) -> None:
    try:
        await notify_task_progress(task, message)
    except Exception as exc:
        print(f"agent-worker notification skipped: {type(exc).__name__}: {exc}")


def _running_status_message(task: AgentTask, status: str) -> str:
    prompt = _short_prompt(task.prompt)
    return "\n".join(
        [
            f"Working: {task.task_id}",
            f"Agent: {task.agent_id}",
            f"Prompt: {prompt}",
            "",
            status,
            "",
            "결과가 준비되면 이 메시지는 최종 결론으로 바뀝니다.",
        ]
    )


def _short_prompt(prompt: str, limit: int = 120) -> str:
    clean = " ".join(prompt.split())
    if len(clean) <= limit:
        return clean
    return f"{clean[: limit - 3].rstrip()}..."


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the always-on AI Shorts agent worker.")
    parser.add_argument(
        "--agent-id",
        action="append",
        dest="agent_ids",
        help="Limit this worker process to one or more agent ids.",
    )
    parser.add_argument("--once", action="store_true", help="Claim at most one task and exit.")
    parser.add_argument("--poll-seconds", default=2.0, type=float)
    args = parser.parse_args()

    asyncio.run(
        run_worker(
            agent_ids=args.agent_ids,
            once=args.once,
            poll_seconds=args.poll_seconds,
        )
    )


if __name__ == "__main__":
    main()
