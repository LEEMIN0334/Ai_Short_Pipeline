from ai_shorts.adapters._stub import StubAdapter
from ai_shorts.agents.runtime.registry import render_agent_catalog
from ai_shorts.agents.runtime.store import (
    AgentTask,
    AgentTaskCreate,
    enqueue_task,
    get_task,
    list_tasks,
)
from ai_shorts.dashboard.store import ProjectCreate, create_project, get_project, list_projects
from ai_shorts.observability.cost_log import make_postgres_sink

KOREAN_RESEARCH = "\ub9ac\uc11c\uce58"
KOREAN_TREND = "\ud2b8\ub80c\ub4dc"
KOREAN_SCRIPT = "\ub300\ubcf8"
KOREAN_SCRIPT_ALT = "\uc2a4\ud06c\ub9bd\ud2b8"
KOREAN_GROK = "\uadf8\ub85d"
KOREAN_CLIP = "\ud074\ub9bd"
KOREAN_DEVELOP = "\uac1c\ubc1c"
KOREAN_DEVELOPER = "\uac1c\ubc1c\uc790"
KOREAN_FEATURE = "\uae30\ub2a5"
KOREAN_ALL = "\uc804\uccb4"
KOREAN_PIPELINE = "\ud30c\uc774\ud504\ub77c\uc778"
KOREAN_VERIFY = "\uac80\uc99d"


async def handle_message(thread_id: str, user_text: str) -> str:
    """Route PM chat messages into direct responses or queued agent work."""

    sink = make_postgres_sink(job_id=thread_id, agent_id="pm")
    stub = StubAdapter(cost_sink=sink)
    normalized = user_text.strip().lower()

    if normalized == "ping":
        result = await stub.do_thing("ping")
        return f"pong (via {result})"

    if normalized in {"agents", "/agents", "help", "/help"}:
        return render_agent_catalog()

    if normalized in {"tasks", "/tasks", "agent tasks", "/agent_tasks"}:
        return await _render_recent_tasks()

    if normalized.startswith(("task ", "/task ")):
        task_id = _strip_command(user_text, ["/task", "task"])
        return await _render_task(task_id)

    queue_request = _agent_queue_request(user_text)
    if queue_request is not None:
        agent_id, command, prompt = queue_request
        task = await enqueue_task(
            AgentTaskCreate(
                requested_by=thread_id,
                agent_id=agent_id,
                command=command,
                prompt=prompt,
                metadata=_task_metadata(thread_id),
            )
        )
        return (
            f"Queued {task.task_id} for {task.agent_id}.\n"
            "The always-on agent worker will post progress updates here.\n"
            f"Check status with: /task {task.task_id}"
        )

    if normalized in {"projects", "/projects", "jobs", "/jobs"}:
        projects = await list_projects(limit=5)
        if not projects:
            return "No shorts jobs yet."
        lines = [
            (
                f"{project.project_id}: {project.title} "
                f"[{project.status.value}] {project.clip_count} clips"
            )
            for project in projects
        ]
        return "\n".join(lines)

    if normalized.startswith(("new ", "/new ", "new:")):
        title = _strip_command(user_text, ["new:", "/new", "new"])
        if not title:
            return "Usage: new <shorts title>"
        new_project = await create_project(ProjectCreate(title=title, topic=title))
        return (
            f"Created {new_project.project_id}: {new_project.title}\n"
            f"Grok loop clips ready: {new_project.clip_count}\n"
            f"Open the dashboard and paste the manual Gemini script when ready."
        )

    if normalized.startswith(("clips ", "/clips ")):
        project_id = _strip_command(user_text, ["/clips", "clips"])
        selected_project = await get_project(project_id)
        if selected_project is None:
            return f"Project not found: {project_id}"
        lines = [f"{selected_project.project_id}: {selected_project.title}"]
        lines.extend(
            f"{clip.clip_index}. {clip.title} [{clip.status.value}] {clip.duration_seconds}s"
            for clip in selected_project.clips
        )
        return "\n".join(lines)

    return f"echo: {user_text}"


def _strip_command(value: str, commands: list[str]) -> str:
    text = value.strip()
    lowered = text.lower()
    for command in commands:
        if lowered.startswith(command):
            return text[len(command) :].strip(" :")
    return ""


def _agent_queue_request(user_text: str) -> tuple[str, str, str] | None:
    normalized = user_text.strip().lower()
    command_map: list[tuple[tuple[str, ...], str, str]] = [
        (("/research ", "research ", "/trend ", "trend "), "research_agent", "research"),
        (
            (f"/{KOREAN_SCRIPT} ", f"{KOREAN_SCRIPT} ", "/script ", "script "),
            "script_writer",
            "script",
        ),
        (
            (f"/{KOREAN_GROK} ", f"{KOREAN_GROK} ", "/grok ", "grok "),
            "grok_planner",
            "grok",
        ),
        (
            (
                f"/{KOREAN_DEVELOP} ",
                f"{KOREAN_DEVELOP} ",
                "/dev ",
                "dev ",
                "/develop ",
                "develop ",
            ),
            "developer_agent",
            "dev",
        ),
        (("/mvp ", "mvp ", "/pipeline ", "pipeline "), "pm_supervisor", "mvp"),
    ]
    for commands, agent_id, command_name in command_map:
        if normalized.startswith(commands):
            prompt = _strip_command(user_text, list(commands))
            if prompt:
                return agent_id, command_name, prompt

    if _contains_any(normalized, [KOREAN_RESEARCH, KOREAN_TREND, "research", "trend"]):
        return "research_agent", "research", user_text.strip()
    if _contains_any(normalized, [KOREAN_SCRIPT, KOREAN_SCRIPT_ALT, "script"]):
        return "script_writer", "script", user_text.strip()
    if _contains_any(normalized, [KOREAN_GROK, KOREAN_CLIP, "grok", "clip", "loop"]):
        return "grok_planner", "grok", user_text.strip()
    if _contains_any(
        normalized,
        [KOREAN_DEVELOP, KOREAN_DEVELOPER, KOREAN_FEATURE, "developer", "develop"],
    ):
        return "developer_agent", "dev", user_text.strip()
    if _contains_any(
        normalized,
        [KOREAN_ALL, KOREAN_PIPELINE, KOREAN_VERIFY, "mvp", "pipeline"],
    ):
        return "pm_supervisor", "mvp", user_text.strip()
    return None


def _contains_any(value: str, needles: list[str]) -> bool:
    return any(needle in value for needle in needles)


def _task_metadata(thread_id: str) -> dict[str, object]:
    if thread_id.startswith("telegram_"):
        return {
            "channel": "telegram",
            "telegram_chat_id": thread_id.removeprefix("telegram_"),
        }
    return {"channel": "local"}


async def _render_recent_tasks() -> str:
    tasks = await list_tasks(limit=8)
    if not tasks:
        return "No agent tasks yet."
    return "\n".join(_task_line(task) for task in tasks)


async def _render_task(task_id: str) -> str:
    if not task_id:
        return "Usage: /task <task_id>"
    task = await get_task(task_id)
    if task is None:
        return f"Task not found: {task_id}"
    lines = [
        _task_line(task),
        f"Prompt: {task.prompt}",
    ]
    if task.result:
        lines.extend(["", task.result])
    if task.error:
        lines.extend(["", f"Error: {task.error}"])
    return "\n".join(lines)


def _task_line(task: AgentTask) -> str:
    return f"{task.task_id}: {task.agent_id} [{task.status.value}] {task.command}"
