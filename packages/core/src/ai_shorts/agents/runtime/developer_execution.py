import asyncio
import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from tempfile import NamedTemporaryFile

from ai_shorts.config import get_settings

ProgressSink = Callable[[str], Awaitable[None]]

EXECUTION_PREFIXES = (
    "실행 승인:",
    "개발 실행:",
    "실제로 개발:",
    "구현 승인:",
    "/execute ",
    "execute ",
    "execute:",
    "/dev execute ",
    "/dev 실행 ",
    "dev execute ",
    "dev 실행 ",
)


def is_developer_execution_request(prompt: str) -> bool:
    normalized = prompt.strip().lower()
    compact = normalized.replace(" ", "")
    return normalized.startswith(EXECUTION_PREFIXES) or compact.startswith(
        ("실행승인:", "개발실행:", "구현승인:")
    )


def strip_developer_execution_prefix(prompt: str) -> str:
    text = prompt.strip()
    lowered = text.lower()
    for prefix in EXECUTION_PREFIXES:
        if lowered.startswith(prefix):
            return text[len(prefix) :].strip(" :")
    for compact_prefix in ("실행승인:", "개발실행:", "구현승인:"):
        compact = lowered.replace(" ", "")
        if compact.startswith(compact_prefix):
            marker = text.find(":")
            if marker >= 0:
                return text[marker + 1 :].strip(" :")
    return text


async def run_developer_execution(
    prompt: str,
    *,
    progress: ProgressSink | None = None,
    runner: Callable[[list[str], Path, str, int], Awaitable[tuple[int, str, str]]] | None = None,
) -> str:
    request = strip_developer_execution_prefix(prompt)
    if not request:
        return _blocked_result("실행할 개발 요청이 비어 있습니다.")

    settings = get_settings()
    repo_root = _repo_root()
    codex_bin = _codex_bin(settings.openclaw_codex_app_server_bin)
    if codex_bin is None:
        return _blocked_result("Codex CLI 실행 파일을 찾지 못했습니다.")

    output_path = _new_output_path()
    system_prompt = _developer_prompt(request)
    command = [
        str(codex_bin),
        "exec",
        "--cd",
        str(repo_root),
        "--sandbox",
        "workspace-write",
        "-c",
        'approval_policy="never"',
        "-m",
        settings.developer_codex_model,
        "--output-last-message",
        str(output_path),
        system_prompt,
    ]

    active_runner = runner or _run_codex_exec
    if progress is not None:
        await progress(
            "[실행] Codex Developer Agent를 시작합니다. 실제 repo 파일을 수정할 수 있습니다."
        )
    execution: asyncio.Future[tuple[int, str, str]] = asyncio.ensure_future(
        active_runner(
            command,
            repo_root,
            str(output_path),
            settings.developer_codex_timeout_seconds,
        )
    )
    elapsed_seconds = 0
    while not execution.done():
        await asyncio.sleep(15)
        elapsed_seconds += 15
        if progress is not None:
            await progress(
                f"[실행 중] Codex가 코드 수정/검증을 진행 중입니다. 경과 {elapsed_seconds}초."
            )
    exit_code, stdout, stderr = await execution
    final_message = _read_output(output_path) or _fallback_output(stdout, stderr)
    status = "succeeded" if exit_code == 0 else "failed"
    return "\n".join(
        [
            f"Developer execution: {request}",
            f"Execution status: {status}",
            f"Exit code: {exit_code}",
            "",
            final_message.strip(),
        ]
    ).strip()


async def _run_codex_exec(
    command: list[str],
    cwd: Path,
    output_path: str,
    timeout_seconds: int,
) -> tuple[int, str, str]:
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout_seconds,
        )
    except TimeoutError:
        process.kill()
        stdout_bytes, stderr_bytes = await process.communicate()
        return (
            124,
            _decode(stdout_bytes),
            f"{_decode(stderr_bytes)}\nTimed out after {timeout_seconds}s.",
        )
    return process.returncode or 0, _decode(stdout_bytes), _decode(stderr_bytes)


def _developer_prompt(request: str) -> str:
    return f"""You are the AI Shorts Pipeline Developer Agent execution mode.

Approved request:
{request}

Operating rules:
- Implement only this approved request.
- Inspect the existing repository before editing.
- Do not read, print, modify, or commit .env files or secrets.
- Do not push, commit, reset, checkout, or overwrite unrelated user changes.
- Keep edits narrowly scoped to the approved behavior.
- Prefer the repo's existing patterns and tests.
- Run focused tests plus ruff/mypy/pytest when practical.
- Perform a self-review before the final answer.
- If the request is too vague or risky, do not edit files; explain the blocker.

Final answer must be in Korean and include:
- changed files
- verification commands/results
- self-review result
- residual risk or next approval needed
"""


def _blocked_result(reason: str) -> str:
    return "\n".join(
        [
            "Developer execution:",
            "Execution status: blocked",
            "Exit code: 1",
            "",
            reason,
        ]
    )


def _repo_root() -> Path:
    configured = os.environ.get("AI_SHORTS_STUDIO_ROOT", "").strip()
    if configured:
        return Path(configured).resolve()
    return Path(__file__).resolve().parents[5]


def _codex_bin(configured: str) -> Path | None:
    candidates = [
        configured,
        os.environ.get("OPENCLAW_CODEX_APP_SERVER_BIN", ""),
        str(Path.home() / "AppData/Local/OpenAI/Codex/bin/codex.exe"),
        "codex",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.name == candidate:
            return path
        if path.exists():
            return path
    return None


def _new_output_path() -> Path:
    output_dir = _repo_root() / ".local_storage" / "developer_agent"
    output_dir.mkdir(parents=True, exist_ok=True)
    handle = NamedTemporaryFile(
        delete=False,
        dir=output_dir,
        prefix="codex-final-",
        suffix=".txt",
        mode="w",
        encoding="utf-8",
    )
    handle.close()
    return Path(handle.name)


def _read_output(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _fallback_output(stdout: str, stderr: str) -> str:
    combined = "\n".join(part for part in [stdout.strip(), stderr.strip()] if part)
    if not combined:
        return "Codex 실행 결과 메시지가 비어 있습니다."
    return combined[-3000:]


def _decode(value: bytes) -> str:
    return value.decode("utf-8", errors="replace")
