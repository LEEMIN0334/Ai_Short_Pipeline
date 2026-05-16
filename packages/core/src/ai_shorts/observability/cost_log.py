import asyncio
import json
from collections.abc import Awaitable, Callable

from ai_shorts.adapters.base import CostEvent
from ai_shorts.storage.postgres import get_conn

_pending_cost_tasks: set[asyncio.Task[None]] = set()


async def write_cost_event(job_id: str, agent_id: str, event: CostEvent) -> None:
    async with get_conn() as conn:
        await conn.execute(
            """
            INSERT INTO cost_log (job_id, agent_id, service, operation, usd, metadata)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb)
            """,
            job_id,
            agent_id,
            event.service,
            event.operation,
            event.usd,
            json.dumps(event.metadata),
        )


def make_postgres_sink(job_id: str, agent_id: str) -> Callable[[CostEvent], Awaitable[None]]:
    async def sink(event: CostEvent) -> None:
        await write_cost_event(job_id=job_id, agent_id=agent_id, event=event)

    return sink


def _forget_done_task(task: asyncio.Task[None]) -> None:
    _pending_cost_tasks.discard(task)


def schedule_cost_write(sink: Callable[[CostEvent], Awaitable[None]], event: CostEvent) -> None:
    task = asyncio.create_task(sink(event))
    _pending_cost_tasks.add(task)
    task.add_done_callback(lambda _: _pending_cost_tasks.discard(task))


async def flush_pending_costs() -> None:
    if not _pending_cost_tasks:
        return
    await asyncio.gather(*list(_pending_cost_tasks))

