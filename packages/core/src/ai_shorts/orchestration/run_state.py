import json
from datetime import UTC, datetime
from enum import StrEnum

from ai_shorts.orchestration.dag import Dag
from ai_shorts.storage.postgres import get_conn


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


async def create_run_state(run_id: str, dag: Dag) -> None:
    async with get_conn() as conn:
        await conn.execute(
            """
            INSERT INTO run_state (run_id, dag_name, status, dag, created_at, updated_at)
            VALUES ($1, $2, $3, $4::jsonb, NOW(), NOW())
            ON CONFLICT (run_id)
            DO UPDATE SET
                dag_name = EXCLUDED.dag_name,
                status = EXCLUDED.status,
                dag = EXCLUDED.dag,
                result = '{}'::jsonb,
                error = NULL,
                started_at = NULL,
                finished_at = NULL,
                updated_at = NOW()
            """,
            run_id,
            dag.name,
            RunStatus.PENDING.value,
            dag.model_dump_json(),
        )


async def mark_run_started(run_id: str, current_task: str | None = None) -> None:
    async with get_conn() as conn:
        await conn.execute(
            """
            UPDATE run_state
            SET status = $2,
                current_task = $3,
                started_at = COALESCE(started_at, $4),
                updated_at = NOW()
            WHERE run_id = $1
            """,
            run_id,
            RunStatus.RUNNING.value,
            current_task,
            datetime.now(UTC),
        )


async def mark_run_finished(
    run_id: str,
    status: RunStatus,
    result: dict[str, object] | None = None,
    error: str | None = None,
) -> None:
    async with get_conn() as conn:
        await conn.execute(
            """
            UPDATE run_state
            SET status = $2,
                result = $3::jsonb,
                error = $4,
                finished_at = NOW(),
                updated_at = NOW()
            WHERE run_id = $1
            """,
            run_id,
            status.value,
            json.dumps(result or {}),
            error,
        )


async def get_run_state(run_id: str) -> dict[str, object] | None:
    async with get_conn() as conn:
        row = await conn.fetchrow(
            """
            SELECT run_id, dag_name, status, current_task, result, error
            FROM run_state
            WHERE run_id = $1
            """,
            run_id,
        )
    if row is None:
        return None
    return dict(row)
