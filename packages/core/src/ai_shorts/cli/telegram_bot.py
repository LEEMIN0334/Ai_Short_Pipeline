import argparse
import asyncio
import re
from enum import StrEnum

import httpx

from ai_shorts.agents.pm.conversational import handle_message
from ai_shorts.agents.runtime.store import merge_task_metadata
from ai_shorts.config import Settings, get_settings


class TelegramBotRole(StrEnum):
    PM = "pm"
    RESEARCH = "research"
    DEVELOPER = "developer"


async def _send_message(
    client: httpx.AsyncClient,
    token: str,
    chat_id: int,
    text: str,
) -> int | None:
    response = await client.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text[:3500]},
    )
    _raise_telegram_error(response, "sendMessage")
    payload = response.json()
    if not isinstance(payload, dict):
        return None
    result = payload.get("result")
    if not isinstance(result, dict):
        return None
    message_id = result.get("message_id")
    return message_id if isinstance(message_id, int) else None


def _allowed_chat_ids(raw_value: str) -> set[int]:
    ids: set[int] = set()
    for part in raw_value.split(","):
        value = part.strip()
        if not value:
            continue
        ids.add(int(value))
    return ids


async def _poll(
    *,
    token: str,
    allowed_chat_ids: set[int],
    role: TelegramBotRole,
) -> None:
    offset = 0
    async with httpx.AsyncClient(timeout=35) as client:
        while True:
            response = await client.get(
                f"https://api.telegram.org/bot{token}/getUpdates",
                params={"timeout": 25, "offset": offset},
            )
            if response.status_code == 409:
                print(
                    f"telegram {role.value} polling conflict: another poller is using this bot."
                )
                await asyncio.sleep(10)
                continue
            _raise_telegram_error(response, "getUpdates")
            payload = response.json()
            if not isinstance(payload, dict):
                await asyncio.sleep(2)
                continue
            updates = payload.get("result", [])
            if not isinstance(updates, list):
                await asyncio.sleep(2)
                continue
            for update in updates:
                if not isinstance(update, dict):
                    continue
                update_id = update.get("update_id")
                if isinstance(update_id, int):
                    offset = update_id + 1
                message = update.get("message")
                if not isinstance(message, dict):
                    continue
                chat = message.get("chat")
                text = message.get("text")
                if not isinstance(chat, dict) or not isinstance(text, str):
                    continue
                chat_id = chat.get("id")
                if not isinstance(chat_id, int):
                    continue
                lowered = text.strip().lower()
                if text.strip().lower() == "/id":
                    await _send_message(client, token, chat_id, f"chat_id={chat_id}")
                    continue
                if lowered in {"/start", "start"}:
                    await _send_message(client, token, chat_id, _start_message(role, chat_id))
                    continue
                if not allowed_chat_ids:
                    await _send_message(
                        client,
                        token,
                        chat_id,
                        "This bot is in ID collection mode. Send /id to register this chat.",
                    )
                    continue
                if chat_id not in allowed_chat_ids:
                    await _send_message(
                        client,
                        token,
                        chat_id,
                        f"This chat is not allowed yet. Send this chat_id to the owner: {chat_id}",
                    )
                    continue
                reply = await _route_message(role, chat_id, text)
                message_id = await _send_message(client, token, chat_id, reply)
                task_id = _queued_task_id(reply)
                if task_id is not None and message_id is not None:
                    await merge_task_metadata(
                        task_id,
                        {
                            "telegram_bot_role": role.value,
                            "telegram_status_message_id": message_id,
                            "telegram_progress_mode": "edit",
                        },
                    )


async def _route_message(role: TelegramBotRole, chat_id: int, text: str) -> str:
    thread_id = f"telegram_{chat_id}"
    routed_text = _role_routed_text(role, text)
    try:
        return await handle_message(thread_id=thread_id, user_text=routed_text)
    except Exception as exc:
        return f"error: {type(exc).__name__}: {exc}"


def _role_routed_text(role: TelegramBotRole, text: str) -> str:
    stripped = text.strip()
    lowered = stripped.lower()

    if role == TelegramBotRole.PM:
        return stripped
    if _is_control_command(lowered):
        return stripped
    if role == TelegramBotRole.RESEARCH:
        if lowered.startswith(("/research ", "research ", "/trend ", "trend ")):
            return stripped
        return f"/research {stripped}"
    if role == TelegramBotRole.DEVELOPER:
        if lowered.startswith(("/dev ", "dev ", "/develop ", "develop ")):
            return stripped
        return f"/dev {stripped}"
    return stripped


def _is_control_command(lowered: str) -> bool:
    return lowered in {
        "/agents",
        "agents",
        "/tasks",
        "tasks",
        "/projects",
        "projects",
        "/start",
        "start",
    } or (
        lowered.startswith("/task ") or lowered.startswith("task ")
    )


def _queued_task_id(reply: str) -> str | None:
    match = re.search(r"\bQueued\s+(task_[A-Za-z0-9]+)\b", reply)
    return match.group(1) if match else None


def _start_message(role: TelegramBotRole, chat_id: int) -> str:
    if role == TelegramBotRole.RESEARCH:
        return (
            "AI Shorts Research Bot connected.\n"
            f"chat_id={chat_id}\n"
            "Send a topic directly, or use /research <topic>."
        )
    if role == TelegramBotRole.DEVELOPER:
        return (
            "AI Shorts Developer Bot connected.\n"
            f"chat_id={chat_id}\n"
            "Send a feature idea directly, or use /dev <feature>."
        )
    return (
        "AI Shorts PM Bot connected.\n"
        f"chat_id={chat_id}\n"
        "Try /agents, /tasks, /research <topic>, /dev <feature>, or /mvp <topic>."
    )


def _raise_telegram_error(response: httpx.Response, operation: str) -> None:
    if response.is_error:
        msg = f"Telegram {operation} failed with HTTP {response.status_code}."
        raise RuntimeError(msg)


def _token_for_role(settings: Settings, role: TelegramBotRole) -> str:
    if role == TelegramBotRole.PM:
        return settings.telegram_bot_token
    if role == TelegramBotRole.RESEARCH:
        return settings.telegram_research_bot_token
    if role == TelegramBotRole.DEVELOPER:
        return settings.telegram_developer_bot_token
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an AI Shorts Telegram bot.")
    parser.add_argument(
        "--bot-role",
        choices=[role.value for role in TelegramBotRole],
        default=TelegramBotRole.PM.value,
    )
    args = parser.parse_args()

    role = TelegramBotRole(args.bot_role)
    settings = get_settings()
    token = _token_for_role(settings, role)
    if not token:
        msg = f"Telegram token is required for bot role: {role.value}"
        raise RuntimeError(msg)
    asyncio.run(
        _poll(
            token=token,
            allowed_chat_ids=_allowed_chat_ids(settings.telegram_allowed_chat_ids),
            role=role,
        )
    )


if __name__ == "__main__":
    main()
