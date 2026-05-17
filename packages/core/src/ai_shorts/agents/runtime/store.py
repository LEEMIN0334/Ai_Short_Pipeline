import json
from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field

from ai_shorts.agents.runtime.registry import AgentDefinition
from ai_shorts.storage.postgres import get_conn


class AgentRuntimeStatus(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    OFFLINE = "offline"
    ERROR = "error"


class AgentTaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentRuntimeRow(BaseModel):
    agent_id: str
    display_name: str
    kind: str
    status: AgentRuntimeStatus
    capabilities: list[str] = Field(default_factory=list)
    heartbeat_at: datetime | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class AgentTaskCreate(BaseModel):
    requested_by: str
    agent_id: str
    prompt: str = Field(min_length=1)
    command: str = ""
    priority: int = 0
    metadata: dict[str, object] = Field(default_factory=dict)


class AgentTask(BaseModel):
    task_id: str
    requested_by: str
    agent_id: str
    command: str
    prompt: str
    status: AgentTaskStatus
    priority: int
    result: str
    error: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


async def register_agent(definition: AgentDefinition) -> AgentRuntimeRow:
    async with get_conn() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO agent_registry (
                agent_id, display_name, kind, status, capabilities, metadata
            )
            VALUES ($1, $2, $3, 'idle', $4, $5::jsonb)
            ON CONFLICT (agent_id) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                kind = EXCLUDED.kind,
                capabilities = EXCLUDED.capabilities,
                metadata = EXCLUDED.metadata,
                updated_at = NOW()
            RETURNING agent_id, display_name, kind, status, capabilities,
                      heartbeat_at, metadata, created_at, updated_at
            """,
            definition.agent_id,
            definition.display_name,
            definition.kind,
            definition.capabilities,
            json.dumps({"description": definition.description}),
        )
    if row is None:
        msg = f"Agent registration failed: {definition.agent_id}"
        raise RuntimeError(msg)
    return _runtime_row(row)


async def register_agents(definitions: tuple[AgentDefinition, ...]) -> list[AgentRuntimeRow]:
    rows: list[AgentRuntimeRow] = []
    for definition in definitions:
        rows.append(await register_agent(definition))
    return rows


async def mark_agent_heartbeat(
    agent_id: str,
    status: AgentRuntimeStatus = AgentRuntimeStatus.IDLE,
) -> None:
    async with get_conn() as conn:
        await conn.execute(
            """
            UPDATE agent_registry
            SET status = $2, heartbeat_at = NOW(), updated_at = NOW()
            WHERE agent_id = $1
            """,
            agent_id,
            status.value,
        )


async def enqueue_task(create: AgentTaskCreate) -> AgentTask:
    task_id = f"task_{uuid4().hex[:12]}"
    async with get_conn() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO agent_task (
                task_id, requested_by, agent_id, command, prompt, priority, metadata
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
            RETURNING task_id, requested_by, agent_id, command, prompt, status,
                      priority, result, error, metadata, created_at, updated_at,
                      started_at, finished_at
            """,
            task_id,
            create.requested_by,
            create.agent_id,
            create.command,
            create.prompt,
            create.priority,
            json.dumps(create.metadata),
        )
    if row is None:
        msg = f"Task enqueue failed: {create.agent_id}"
        raise RuntimeError(msg)
    return _task_row(row)


async def claim_next_task(agent_ids: list[str] | None = None) -> AgentTask | None:
    async with get_conn() as conn:
        row = await conn.fetchrow(
            """
            UPDATE agent_task
            SET status = 'running',
                started_at = COALESCE(started_at, NOW()),
                updated_at = NOW()
            WHERE id = (
                SELECT id
                FROM agent_task
                WHERE status = 'queued'
                  AND ($1::text[] IS NULL OR agent_id = ANY($1::text[]))
                ORDER BY priority DESC, created_at ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING task_id, requested_by, agent_id, command, prompt, status,
                      priority, result, error, metadata, created_at, updated_at,
                      started_at, finished_at
            """,
            agent_ids,
        )
    return _task_row(row) if row is not None else None


async def mark_task_succeeded(task_id: str, result: str) -> AgentTask:
    return await _finish_task(
        task_id=task_id,
        status=AgentTaskStatus.SUCCEEDED,
        result=result,
        error=None,
    )


async def mark_task_failed(task_id: str, error: str) -> AgentTask:
    return await _finish_task(
        task_id=task_id,
        status=AgentTaskStatus.FAILED,
        result="",
        error=error,
    )


async def get_task(task_id: str) -> AgentTask | None:
    async with get_conn() as conn:
        row = await conn.fetchrow(
            """
            SELECT task_id, requested_by, agent_id, command, prompt, status,
                   priority, result, error, metadata, created_at, updated_at,
                   started_at, finished_at
            FROM agent_task
            WHERE task_id = $1
            """,
            task_id,
        )
    return _task_row(row) if row is not None else None


async def get_latest_task(
    requested_by: str,
    *,
    agent_id: str | None = None,
    status: AgentTaskStatus | None = None,
) -> AgentTask | None:
    async with get_conn() as conn:
        row = await conn.fetchrow(
            """
            SELECT task_id, requested_by, agent_id, command, prompt, status,
                   priority, result, error, metadata, created_at, updated_at,
                   started_at, finished_at
            FROM agent_task
            WHERE requested_by = $1
              AND ($2::text IS NULL OR agent_id = $2)
              AND ($3::text IS NULL OR status = $3)
            ORDER BY created_at DESC
            LIMIT 1
            """,
            requested_by,
            agent_id,
            status.value if status is not None else None,
        )
    return _task_row(row) if row is not None else None


async def merge_task_metadata(task_id: str, metadata: dict[str, object]) -> AgentTask:
    async with get_conn() as conn:
        row = await conn.fetchrow(
            """
            UPDATE agent_task
            SET metadata = metadata || $2::jsonb,
                updated_at = NOW()
            WHERE task_id = $1
            RETURNING task_id, requested_by, agent_id, command, prompt, status,
                      priority, result, error, metadata, created_at, updated_at,
                      started_at, finished_at
            """,
            task_id,
            json.dumps(metadata),
        )
    if row is None:
        msg = f"Task not found: {task_id}"
        raise RuntimeError(msg)
    return _task_row(row)


async def list_tasks(limit: int = 10) -> list[AgentTask]:
    async with get_conn() as conn:
        rows = await conn.fetch(
            """
            SELECT task_id, requested_by, agent_id, command, prompt, status,
                   priority, result, error, metadata, created_at, updated_at,
                   started_at, finished_at
            FROM agent_task
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )
    return [_task_row(row) for row in rows]


async def _finish_task(
    *,
    task_id: str,
    status: AgentTaskStatus,
    result: str,
    error: str | None,
) -> AgentTask:
    async with get_conn() as conn:
        row = await conn.fetchrow(
            """
            UPDATE agent_task
            SET status = $2,
                result = $3,
                error = $4,
                finished_at = NOW(),
                updated_at = NOW()
            WHERE task_id = $1
            RETURNING task_id, requested_by, agent_id, command, prompt, status,
                      priority, result, error, metadata, created_at, updated_at,
                      started_at, finished_at
            """,
            task_id,
            status.value,
            result,
            error,
        )
    if row is None:
        msg = f"Task not found: {task_id}"
        raise RuntimeError(msg)
    return _task_row(row)


def _runtime_row(row: object) -> AgentRuntimeRow:
    value = _row_dict(row)
    return AgentRuntimeRow(
        agent_id=str(value["agent_id"]),
        display_name=str(value["display_name"]),
        kind=str(value["kind"]),
        status=AgentRuntimeStatus(str(value["status"])),
        capabilities=_string_list(value["capabilities"]),
        heartbeat_at=_optional_datetime(value["heartbeat_at"]),
        metadata=_json_dict(value["metadata"]),
        created_at=_datetime_value(value["created_at"]),
        updated_at=_datetime_value(value["updated_at"]),
    )


def _task_row(row: object) -> AgentTask:
    value = _row_dict(row)
    return AgentTask(
        task_id=str(value["task_id"]),
        requested_by=str(value["requested_by"]),
        agent_id=str(value["agent_id"]),
        command=str(value["command"]),
        prompt=str(value["prompt"]),
        status=AgentTaskStatus(str(value["status"])),
        priority=_int_value(value["priority"]),
        result=str(value["result"]),
        error=_optional_str(value["error"]),
        metadata=_json_dict(value["metadata"]),
        created_at=_datetime_value(value["created_at"]),
        updated_at=_datetime_value(value["updated_at"]),
        started_at=_optional_datetime(value["started_at"]),
        finished_at=_optional_datetime(value["finished_at"]),
    )


def _row_dict(row: object) -> dict[str, object]:
    if hasattr(row, "items"):
        return {str(key): value for key, value in row.items()}
    if isinstance(row, dict):
        return row
    msg = f"Unsupported row type: {type(row).__name__}"
    raise TypeError(msg)


def _datetime_value(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    msg = f"Expected datetime, got {type(value).__name__}"
    raise TypeError(msg)


def _optional_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    return _datetime_value(value)


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    msg = f"Expected int, got {type(value).__name__}"
    raise TypeError(msg)


def _json_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return {str(key): item for key, item in value.items()}
    if isinstance(value, str):
        loaded = json.loads(value)
        if isinstance(loaded, dict):
            return {str(key): item for key, item in loaded.items()}
    return {}


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, tuple):
        return [str(item) for item in value]
    return []
