import asyncio
import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from tempfile import NamedTemporaryFile

from ai_shorts.config import get_settings

ProgressSink = Callable[[str], Awaitable[None]]
Runner = Callable[[list[str], Path, str, int], Awaitable[tuple[int, str, str]]]


async def run_web_research(
    prompt: str,
    *,
    progress: ProgressSink | None = None,
    runner: Runner | None = None,
) -> str:
    query = " ".join(prompt.strip().split())
    if not query:
        return _blocked_result("리서치 질문이 비어 있습니다.")

    settings = get_settings()
    repo_root = _repo_root()
    codex_bin = _codex_bin(settings.openclaw_codex_app_server_bin)
    if codex_bin is None:
        return _blocked_result("Codex CLI 실행 파일을 찾지 못했습니다.")

    output_path = _new_output_path()
    command = [
        str(codex_bin),
        "--search",
        "exec",
        "--cd",
        str(repo_root),
        "--sandbox",
        "read-only",
        "-c",
        'approval_policy="never"',
        "-m",
        settings.research_codex_model,
        "--output-last-message",
        str(output_path),
        _research_prompt(query),
    ]

    active_runner = runner or _run_codex_exec
    if progress is not None:
        await progress("[웹 검색 중] Codex Research Agent가 공개 웹 자료를 조사합니다.")
    execution: asyncio.Future[tuple[int, str, str]] = asyncio.ensure_future(
        active_runner(
            command,
            repo_root,
            str(output_path),
            settings.research_codex_timeout_seconds,
        )
    )
    elapsed_seconds = 0
    while not execution.done():
        await asyncio.sleep(15)
        elapsed_seconds += 15
        if progress is not None:
            await progress(
                f"[리서치 진행 중] 웹 검색/출처 검토/요약 작성 중입니다. 경과 {elapsed_seconds}초."
            )

    exit_code, stdout, stderr = await execution
    final_message = _read_output(output_path) or _fallback_output(stdout, stderr)
    status = "succeeded" if exit_code == 0 else "failed"
    return "\n".join(
        [
            f"Web research: {query}",
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


def _research_prompt(query: str) -> str:
    return f"""You are the AI Shorts Pipeline Research Agent.

Research request:
{query}

Role boundary:
- You are a pure web research agent.
- Do not use Instagram/YouTube trend scouting as your default method.
- Trend Scout owns platform trend candidate discovery.
- Your job is to search the public web, compare sources, synthesize findings, and hand off evidence.

Operating rules:
- Use web search for current or factual claims.
- Prefer primary sources, official docs, pricing pages, papers, credible reporting,
  and direct product pages.
- Include source links for factual claims.
- Separate confirmed facts from assumptions.
- Do not implement code, publish content, upload files, spend money, or read .env/secrets.
- If the web search is insufficient, say exactly what is missing.

Final answer must be in Korean and include:
- 리서치 질문
- 핵심 결론
- 근거/출처 링크
- 비교 또는 판단 기준
- PM이 결정해야 할 것
- 다음 액션
"""


def _blocked_result(reason: str) -> str:
    return "\n".join(
        [
            "Web research:",
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
    output_dir = _repo_root() / ".local_storage" / "research_agent"
    output_dir.mkdir(parents=True, exist_ok=True)
    handle = NamedTemporaryFile(
        delete=False,
        dir=output_dir,
        prefix="codex-research-",
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
        return "Codex 리서치 실행 결과 메시지가 비어 있습니다."
    return combined[-3000:]


def _decode(value: bytes) -> str:
    return value.decode("utf-8", errors="replace")
