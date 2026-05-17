from ai_shorts.adapters._stub import StubAdapter
from ai_shorts.agents.runtime.registry import render_agent_catalog
from ai_shorts.agents.runtime.store import (
    AgentTask,
    AgentTaskCreate,
    AgentTaskStatus,
    enqueue_task,
    get_latest_task,
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
KOREAN_FOLLOWUP_TERMS = (
    "\uc774\uc5b4\uc11c",
    "\uacc4\uc18d",
    "\ub354 \uc790\uc138\ud788",
    "\uc790\uc138\ud788",
    "\ucd94\uac00\ub85c",
    "\uc704 \ub0b4\uc6a9",
    "\ubc29\uae08",
    "\uc544\uae4c",
    "\uadf8 \uacb0\uacfc",
    "\uadf8 \ub9ac\uc11c\uce58",
    "\uc774 \ub9ac\uc11c\uce58",
    "\uc774\uc804",
    "\uc804 \ub9ac\uc11c\uce58",
    "\uc55e\uc5d0\uc11c",
    "1\ubc88",
    "2\ubc88",
    "3\ubc88",
    "\uccab \ubc88\uc9f8",
    "\ub450 \ubc88\uc9f8",
    "\uc138 \ubc88\uc9f8",
)


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

    queue_request = await _resolve_queue_request(thread_id, user_text)
    if queue_request is not None:
        agent_id, command, prompt, context_metadata = queue_request
        metadata = _task_metadata(thread_id)
        metadata.update(context_metadata)
        task = await enqueue_task(
            AgentTaskCreate(
                requested_by=thread_id,
                agent_id=agent_id,
                command=command,
                prompt=prompt,
                metadata=metadata,
            )
        )
        context_line = ""
        if "context_task_id" in metadata:
            context_line = f"\nContext: continuing from {metadata['context_task_id']}."
        return (
            f"Queued {task.task_id} for {task.agent_id}.\n"
            "The always-on agent worker will post progress updates here.\n"
            f"Check status with: /task {task.task_id}"
            f"{context_line}"
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
        (("/research ", "research "), "research_agent", "research"),
        (("/trend ", "trend "), "trend_scout", "trend"),
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

    if _contains_any(normalized, [KOREAN_RESEARCH, "research"]):
        return "research_agent", "research", user_text.strip()
    if _contains_any(normalized, [KOREAN_TREND, "trend"]):
        return "trend_scout", "trend", user_text.strip()
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


async def _resolve_queue_request(
    thread_id: str,
    user_text: str,
) -> tuple[str, str, str, dict[str, object]] | None:
    queue_request = _agent_queue_request(user_text)
    if queue_request is not None:
        agent_id, command, prompt = queue_request
        context = await _latest_context_task(thread_id, agent_id, prompt)
        prompt, metadata = _prompt_with_context(prompt, context)
        return agent_id, command, prompt, metadata

    prompt = user_text.strip()
    if not _looks_like_followup(prompt):
        return None
    previous = await get_latest_task(
        thread_id,
        status=AgentTaskStatus.SUCCEEDED,
    )
    if previous is None or not previous.result.strip():
        return None
    prompt, metadata = _prompt_with_context(prompt, previous)
    return previous.agent_id, previous.command or "followup", prompt, metadata


async def _latest_context_task(
    thread_id: str,
    agent_id: str,
    prompt: str,
) -> AgentTask | None:
    if not _looks_like_followup(prompt):
        return None
    previous = await get_latest_task(
        thread_id,
        agent_id=agent_id,
        status=AgentTaskStatus.SUCCEEDED,
    )
    if previous is None or not previous.result.strip():
        return None
    return previous


def _prompt_with_context(prompt: str, previous: AgentTask | None) -> tuple[str, dict[str, object]]:
    if previous is None:
        return prompt, {}
    context = _context_prompt(prompt, previous)
    return context, {
        "context_task_id": previous.task_id,
        "context_agent_id": previous.agent_id,
        "context_mode": "agent_followup",
    }


def _looks_like_followup(prompt: str) -> bool:
    normalized = " ".join(prompt.strip().lower().split())
    if not normalized:
        return False
    if any(term in normalized for term in KOREAN_FOLLOWUP_TERMS):
        return True
    if any(term in normalized for term in ("continue", "follow up", "deeper", "more detail")):
        return True
    short_reference_terms = (
        "\uc774\uac70",
        "\uadf8\uac70",
        "\uc704",
        "\uc774\uac83",
        "\uadf8\uac83",
    )
    return len(normalized) <= 80 and any(term in normalized for term in short_reference_terms)


def _context_prompt(prompt: str, previous: AgentTask) -> str:
    previous_result = _excerpt(previous.result, limit=6000)
    return "\n".join(
        [
            "Follow-up request:",
            prompt.strip(),
            "",
            f"Previous task: {previous.task_id}",
            f"Previous agent: {previous.agent_id}",
            f"Previous command: {previous.command}",
            f"Previous prompt: {previous.prompt}",
            "",
            "Previous result excerpt:",
            previous_result,
            "",
            "Use the previous result as conversation context.",
            "Answer the follow-up directly.",
            "If new factual claims are needed, refresh or verify them instead of assuming.",
            "Say what changed from the previous result.",
        ]
    ).strip()


def _excerpt(value: str, *, limit: int) -> str:
    clean = value.strip()
    if len(clean) <= limit:
        return clean
    split_at = clean.rfind("\n\n", 0, limit)
    if split_at < limit // 2:
        split_at = clean.rfind("\n", 0, limit)
    if split_at < limit // 2:
        split_at = clean.rfind(" ", 0, limit)
    if split_at < limit // 2:
        split_at = limit
    return clean[:split_at].rstrip()


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
