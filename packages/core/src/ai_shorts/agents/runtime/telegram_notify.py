import httpx

from ai_shorts.agents.runtime.store import AgentTask
from ai_shorts.config import get_settings

TELEGRAM_MESSAGE_LIMIT = 3500


async def notify_task_progress(task: AgentTask, message: str) -> None:
    chat_id = _telegram_chat_id(task)
    if chat_id is None:
        return
    token = _telegram_token_for_task(task)
    if not token:
        return
    await _send_telegram_chat_action(token, chat_id)
    chunks = _split_message(message)
    message_id = _telegram_status_message_id(task)
    if message_id is not None:
        await _edit_telegram_message(token, chat_id, message_id, chunks[0])
        for chunk in chunks[1:]:
            await _send_telegram_message(token, chat_id, chunk)
        return
    for chunk in chunks:
        await _send_telegram_message(token, chat_id, chunk)


def summarize_task_result(task: AgentTask, result: str) -> str:
    if task.agent_id == "pm_supervisor":
        if "Final QC: pass" in result:
            return (
                f"Done: {task.task_id}\n"
                "Conclusion: local MVP gate passed. QC approved the preview plan.\n"
                f"Details: /task {task.task_id}"
            )
        return (
            f"Done: {task.task_id}\n"
            "Conclusion: MVP preview finished, but it needs review.\n"
            f"Details: /task {task.task_id}"
        )

    if task.agent_id == "trend_scout":
        ready = "ready for generation" if "Ready for generation: yes" in result else "needs review"
        return (
            f"Done: {task.task_id}\n"
            f"Conclusion: trend scout preview is {ready}.\n"
            f"Details: /task {task.task_id}"
        )

    if task.agent_id == "research_agent":
        if result.startswith("Research Agent intro:"):
            return _intro_summary(task, result)
        return _web_research_summary(task, result)

    if task.agent_id == "script_writer":
        return (
            f"Done: {task.task_id}\n"
            "Conclusion: script preview and timed segments are ready.\n"
            f"Details: /task {task.task_id}"
        )

    if task.agent_id == "developer_agent":
        if result.startswith("Developer Agent intro:"):
            return _intro_summary(task, result)
        if result.startswith("Developer execution:"):
            return _developer_execution_summary(task, result)
        return (
            f"Done: {task.task_id}\n"
            "Conclusion: developer plan and self-review gate are ready for PM approval.\n"
            f"Details: /task {task.task_id}"
        )

    if task.agent_id == "grok_planner":
        return (
            f"Done: {task.task_id}\n"
            "Conclusion: Grok loop clip prompts are ready for manual generation.\n"
            f"Details: /task {task.task_id}"
        )

    if task.agent_id in {"composer", "qc_agent"}:
        return (
            f"Done: {task.task_id}\n"
            "Conclusion: composition/QC preview finished.\n"
            f"Details: /task {task.task_id}"
        )

    return (
        f"Done: {task.task_id}\n"
        "Conclusion: task finished.\n"
        f"Details: /task {task.task_id}"
    )


def summarize_task_error(task: AgentTask, error: str) -> str:
    return (
        f"Failed: {task.task_id}\n"
        f"Agent: {task.agent_id}\n"
        f"Conclusion: task failed with {error[:220]}\n"
        f"Details: /task {task.task_id}"
    )


def _intro_summary(task: AgentTask, result: str) -> str:
    body = _strip_intro_header(result)
    return (
        f"완료: {task.task_id}\n\n"
        f"{body}\n\n"
        f"자세히 보기: /task {task.task_id}"
    )


def _strip_intro_header(result: str) -> str:
    lines = result.splitlines()
    if lines and lines[0].strip().endswith("intro:"):
        lines = lines[1:]
    body = "\n".join(line for line in lines).strip()
    return body or "자기소개 응답이 준비되었습니다."


def _developer_execution_summary(task: AgentTask, result: str) -> str:
    status = "확인 필요"
    if "Execution status: succeeded" in result:
        status = "완료"
    elif "Execution status: blocked" in result:
        status = "보류"
    body, omitted = _preview(result, limit=3000)
    note = (
        f"\n\n전체 결과는 /task {task.task_id}에서 여러 메시지로 나눠 볼 수 있습니다."
        if omitted
        else ""
    )
    return (
        f"{status}: {task.task_id}\n\n"
        f"{body}{note}\n\n"
        f"자세히 보기: /task {task.task_id}"
    )


def _web_research_summary(task: AgentTask, result: str) -> str:
    status = "확인 필요"
    if "Execution status: succeeded" in result:
        status = "완료"
    elif "Execution status: blocked" in result:
        status = "보류"
    body, omitted = _preview(result, limit=3000)
    note = (
        f"\n\n전체 리서치 원문은 /task {task.task_id}에서 여러 메시지로 나눠 볼 수 있습니다."
        if omitted
        else ""
    )
    return (
        f"{status}: {task.task_id}\n\n"
        f"{body}{note}\n\n"
        f"자세히 보기: /task {task.task_id}"
    )


async def _send_telegram_message(token: str, chat_id: str, text: str) -> None:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
        )
        _raise_telegram_error(response, "sendMessage")


async def _edit_telegram_message(token: str, chat_id: str, message_id: int, text: str) -> None:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            f"https://api.telegram.org/bot{token}/editMessageText",
            json={"chat_id": chat_id, "message_id": message_id, "text": text},
        )
        if response.status_code == 400 and "message is not modified" in response.text:
            return
        _raise_telegram_error(response, "editMessageText")


async def _send_telegram_chat_action(token: str, chat_id: str) -> None:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"https://api.telegram.org/bot{token}/sendChatAction",
            json={"chat_id": chat_id, "action": "typing"},
        )
        _raise_telegram_error(response, "sendChatAction")


def _telegram_token_for_task(task: AgentTask) -> str:
    settings = get_settings()
    role = str(task.metadata.get("telegram_bot_role") or "").strip().lower()
    if role == "research":
        return settings.telegram_research_bot_token or settings.telegram_bot_token
    if role == "developer":
        return settings.telegram_developer_bot_token or settings.telegram_bot_token
    return settings.telegram_bot_token


def _raise_telegram_error(response: httpx.Response, operation: str) -> None:
    if response.is_error:
        msg = f"Telegram {operation} failed with HTTP {response.status_code}."
        raise RuntimeError(msg)


def _telegram_chat_id(task: AgentTask) -> str | None:
    value = task.metadata.get("telegram_chat_id")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str) and value.strip():
        return value.strip()
    if task.requested_by.startswith("telegram_"):
        chat_id = task.requested_by.removeprefix("telegram_").strip()
        return chat_id or None
    return None


def _telegram_status_message_id(task: AgentTask) -> int | None:
    value = task.metadata.get("telegram_status_message_id")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    return None


def _split_message(text: str, *, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    clean = text.strip() or " "
    if len(clean) <= limit:
        return [clean]

    payload_limit = max(limit - 24, 1)
    chunks: list[str] = []
    remaining = clean
    while remaining:
        if len(remaining) <= payload_limit:
            chunks.append(remaining)
            break
        split_at = remaining.rfind("\n\n", 0, payload_limit)
        if split_at < payload_limit // 2:
            split_at = remaining.rfind("\n", 0, payload_limit)
        if split_at < payload_limit // 2:
            split_at = remaining.rfind(" ", 0, payload_limit)
        if split_at < 1:
            split_at = payload_limit
        chunk = remaining[:split_at].rstrip()
        chunks.append(chunk or remaining[:payload_limit])
        remaining = remaining[split_at:].lstrip()

    total = len(chunks)
    return [f"[{index}/{total}]\n{chunk}" for index, chunk in enumerate(chunks, start=1)]


def _preview(message: str, *, limit: int) -> tuple[str, bool]:
    clean = message.strip()
    if len(clean) <= limit:
        return clean, False
    split_at = clean.rfind("\n\n", 0, limit)
    if split_at < limit // 2:
        split_at = clean.rfind("\n", 0, limit)
    if split_at < limit // 2:
        split_at = clean.rfind(" ", 0, limit)
    if split_at < limit // 2:
        split_at = limit
    return clean[:split_at].rstrip(), True
