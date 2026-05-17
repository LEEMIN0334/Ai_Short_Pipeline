import json
from datetime import datetime
from enum import StrEnum
from math import ceil
from uuid import uuid4

from pydantic import BaseModel, Field

from ai_shorts.storage.postgres import get_conn


class ProjectStatus(StrEnum):
    IDEA = "idea"
    SCRIPTING = "scripting"
    CLIPS = "clips"
    ASSEMBLY = "assembly"
    REVIEW = "review"
    COMPLETE = "complete"
    PAUSED = "paused"


class ClipStatus(StrEnum):
    TODO = "todo"
    PROMPT_READY = "prompt_ready"
    GENERATED = "generated"
    APPROVED = "approved"
    REJECTED = "rejected"


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=140)
    topic: str = Field(default="", max_length=500)
    target_duration_seconds: int = Field(default=45, ge=10, le=180)
    manual_script: str = ""
    notes: str = ""
    clip_count: int | None = Field(default=None, ge=1, le=12)


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=140)
    topic: str | None = Field(default=None, max_length=500)
    status: ProjectStatus | None = None
    target_duration_seconds: int | None = Field(default=None, ge=10, le=180)
    manual_script: str | None = None
    notes: str | None = None


class ClipUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=140)
    prompt: str | None = None
    first_frame_prompt: str | None = None
    last_frame_prompt: str | None = None
    status: ClipStatus | None = None
    duration_seconds: int | None = Field(default=None, ge=5, le=15)
    video_uri: str | None = None
    loop_match_notes: str | None = None


class GrokClip(BaseModel):
    clip_id: str
    project_id: str
    clip_index: int
    title: str
    prompt: str
    first_frame_prompt: str
    last_frame_prompt: str
    status: ClipStatus
    duration_seconds: int
    video_uri: str
    loop_match_notes: str
    created_at: datetime
    updated_at: datetime


class ProjectSummary(BaseModel):
    project_id: str
    title: str
    topic: str
    status: ProjectStatus
    target_duration_seconds: int
    manual_script: str
    notes: str
    clip_count: int = 0
    created_at: datetime
    updated_at: datetime
    clips: list[GrokClip] = Field(default_factory=list)


class CostLogRow(BaseModel):
    job_id: str
    agent_id: str
    service: str
    operation: str
    usd: str
    created_at: datetime


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


def _clip_count(target_duration_seconds: int, requested: int | None) -> int:
    if requested is not None:
        return requested
    return min(12, max(1, ceil(target_duration_seconds / 12)))


def _loop_prompt(project: ProjectCreate, clip_index: int, clip_count: int) -> str:
    topic = project.topic.strip() or project.title.strip()
    return (
        f"Create a 10-15 second vertical 9:16 Grok video loop for '{topic}'. "
        f"This is clip {clip_index} of {clip_count}. Keep the opening and closing frame "
        "visually similar so the clip can loop cleanly. Use one clear subject, a stable "
        "camera angle, consistent lighting, and no text overlays."
    )


async def create_project(project: ProjectCreate) -> ProjectSummary:
    project_id = _new_id("short")
    clip_count = _clip_count(project.target_duration_seconds, project.clip_count)
    async with get_conn() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO shorts_project (
                    project_id, title, topic, target_duration_seconds, manual_script, notes
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                project_id,
                project.title.strip(),
                project.topic.strip(),
                project.target_duration_seconds,
                project.manual_script,
                project.notes,
            )
            for index in range(1, clip_count + 1):
                title = f"Loop clip {index:02d}"
                prompt = _loop_prompt(project, index, clip_count)
                await conn.execute(
                    """
                    INSERT INTO grok_clip (
                        clip_id,
                        project_id,
                        clip_index,
                        title,
                        prompt,
                        first_frame_prompt,
                        last_frame_prompt,
                        status,
                        duration_seconds
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, 'prompt_ready', 12)
                    """,
                    _new_id("clip"),
                    project_id,
                    index,
                    title,
                    prompt,
                    "Match the first clear frame of the clip.",
                    "Return to the same composition as the first frame.",
                )
    result = await get_project(project_id)
    if result is None:
        msg = f"Project was not created: {project_id}"
        raise RuntimeError(msg)
    return result


async def list_projects(limit: int = 50) -> list[ProjectSummary]:
    async with get_conn() as conn:
        rows = await conn.fetch(
            """
            SELECT
                p.project_id,
                p.title,
                p.topic,
                p.status,
                p.target_duration_seconds,
                p.manual_script,
                p.notes,
                p.created_at,
                p.updated_at,
                COUNT(c.id)::int AS clip_count
            FROM shorts_project p
            LEFT JOIN grok_clip c ON c.project_id = p.project_id
            GROUP BY p.project_id, p.title, p.topic, p.status, p.target_duration_seconds,
                     p.manual_script, p.notes, p.created_at, p.updated_at
            ORDER BY p.updated_at DESC
            LIMIT $1
            """,
            limit,
        )
    return [_project_from_row(row) for row in rows]


async def get_project(project_id: str) -> ProjectSummary | None:
    async with get_conn() as conn:
        project_row = await conn.fetchrow(
            """
            SELECT
                project_id,
                title,
                topic,
                status,
                target_duration_seconds,
                manual_script,
                notes,
                created_at,
                updated_at,
                0::int AS clip_count
            FROM shorts_project
            WHERE project_id = $1
            """,
            project_id,
        )
        if project_row is None:
            return None
        clip_rows = await conn.fetch(
            """
            SELECT clip_id, project_id, clip_index, title, prompt, first_frame_prompt,
                   last_frame_prompt, status, duration_seconds, video_uri,
                   loop_match_notes, created_at, updated_at
            FROM grok_clip
            WHERE project_id = $1
            ORDER BY clip_index
            """,
            project_id,
        )
    project = _project_from_row(project_row)
    project.clips = [_clip_from_row(row) for row in clip_rows]
    project.clip_count = len(project.clips)
    return project


async def update_project(project_id: str, update: ProjectUpdate) -> ProjectSummary | None:
    current = await get_project(project_id)
    if current is None:
        return None
    values = update.model_dump(exclude_unset=True)
    if not values:
        return current
    assignments: list[str] = []
    params: list[object] = []
    for index, (key, value) in enumerate(values.items(), start=1):
        assignments.append(f"{key} = ${index}")
        params.append(value.value if isinstance(value, StrEnum) else value)
    params.append(project_id)
    sql = (
        "UPDATE shorts_project SET "
        + ", ".join(assignments)
        + f", updated_at = NOW() WHERE project_id = ${len(params)}"
    )
    async with get_conn() as conn:
        await conn.execute(sql, *params)
    return await get_project(project_id)


async def update_clip(clip_id: str, update: ClipUpdate) -> GrokClip | None:
    values = update.model_dump(exclude_unset=True)
    if not values:
        return await _get_clip(clip_id)
    assignments: list[str] = []
    params: list[object] = []
    for index, (key, value) in enumerate(values.items(), start=1):
        assignments.append(f"{key} = ${index}")
        params.append(value.value if isinstance(value, StrEnum) else value)
    params.append(clip_id)
    sql = (
        "UPDATE grok_clip SET "
        + ", ".join(assignments)
        + f", updated_at = NOW() WHERE clip_id = ${len(params)}"
    )
    async with get_conn() as conn:
        row = await conn.fetchrow(sql + " RETURNING *", *params)
    if row is None:
        return None
    return _clip_from_row(row)


async def list_recent_costs(limit: int = 10) -> list[CostLogRow]:
    async with get_conn() as conn:
        rows = await conn.fetch(
            """
            SELECT job_id, agent_id, service, operation, usd::text AS usd, created_at
            FROM cost_log
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )
    return [
        CostLogRow(
            job_id=row["job_id"],
            agent_id=row["agent_id"],
            service=row["service"],
            operation=row["operation"],
            usd=row["usd"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


async def _get_clip(clip_id: str) -> GrokClip | None:
    async with get_conn() as conn:
        row = await conn.fetchrow("SELECT * FROM grok_clip WHERE clip_id = $1", clip_id)
    if row is None:
        return None
    return _clip_from_row(row)


def _project_from_row(row: object) -> ProjectSummary:
    value = _row_dict(row)
    return ProjectSummary(
        project_id=str(value["project_id"]),
        title=str(value["title"]),
        topic=str(value["topic"]),
        status=ProjectStatus(str(value["status"])),
        target_duration_seconds=_int_value(value["target_duration_seconds"]),
        manual_script=str(value["manual_script"]),
        notes=str(value["notes"]),
        clip_count=_int_value(value.get("clip_count", 0)),
        created_at=_datetime_value(value["created_at"]),
        updated_at=_datetime_value(value["updated_at"]),
    )


def _clip_from_row(row: object) -> GrokClip:
    value = _row_dict(row)
    return GrokClip(
        clip_id=str(value["clip_id"]),
        project_id=str(value["project_id"]),
        clip_index=_int_value(value["clip_index"]),
        title=str(value["title"]),
        prompt=str(value["prompt"]),
        first_frame_prompt=str(value["first_frame_prompt"]),
        last_frame_prompt=str(value["last_frame_prompt"]),
        status=ClipStatus(str(value["status"])),
        duration_seconds=_int_value(value["duration_seconds"]),
        video_uri=str(value["video_uri"]),
        loop_match_notes=str(value["loop_match_notes"]),
        created_at=_datetime_value(value["created_at"]),
        updated_at=_datetime_value(value["updated_at"]),
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


def _int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    msg = f"Expected int, got {type(value).__name__}"
    raise TypeError(msg)


def json_dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)
