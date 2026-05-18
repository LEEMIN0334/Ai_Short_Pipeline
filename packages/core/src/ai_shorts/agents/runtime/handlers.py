import asyncio
from collections.abc import Awaitable, Callable

from ai_shorts.agents.runtime.developer_execution import (
    is_developer_execution_request,
    run_developer_execution,
)
from ai_shorts.agents.runtime.preview import (
    build_developer_preview,
    build_grok_prompt_preview,
    build_mvp_preview,
    build_script_preview,
    build_trend_scout_preview,
)
from ai_shorts.agents.runtime.registry import render_agent_catalog
from ai_shorts.agents.runtime.research_execution import run_web_research
from ai_shorts.agents.runtime.store import AgentTask

ProgressSink = Callable[[str], Awaitable[None]]


async def execute_agent_task(
    task: AgentTask,
    progress: ProgressSink | None = None,
    *,
    progress_delay_seconds: float = 0.0,
) -> str:
    prompt = _clean_prompt(task.prompt)

    if _is_self_intro_prompt(prompt):
        await _emit_stages(
            progress,
            [
                "[1/3] 요청을 확인했습니다. 자기소개 요청으로 인식했습니다.",
                "[2/3] 역할과 PM 연결 방식을 정리하고 있습니다.",
                "[3/3] 사용자가 바로 이해할 수 있게 답변을 작성합니다.",
            ],
            delay_seconds=progress_delay_seconds,
        )
        return _agent_intro(task.agent_id)

    if task.agent_id == "pm_supervisor":
        await _emit_stages(
            progress,
            [
                "[1/5] 요청을 분석하고 목표와 필요한 하위 agent를 정리합니다.",
                "[2/5] Trend Scout와 Research Agent의 작업 범위를 잡습니다.",
                "[3/5] Script Writer와 Splitter가 쓸 장면 구조를 준비합니다.",
                "[4/5] Composer가 자막, 음성, 영상 결합 계획을 확인합니다.",
                "[5/5] QC Agent가 승인 또는 재시도 기준을 평가합니다.",
            ],
            delay_seconds=progress_delay_seconds,
        )
        return await build_mvp_preview(prompt)
    if task.agent_id == "trend_scout":
        await _emit_stages(
            progress,
            [
                "[1/4] 요청을 분석하고 트렌드 후보를 찾을 주제를 정리합니다.",
                "[2/4] Instagram/YouTube 후보 신호를 확인합니다.",
                "[3/4] 조회수, 반응, 최신성을 기준으로 후보를 점수화합니다.",
                "[4/4] 중복을 제거하고 Research Agent에 넘길 후보만 남깁니다.",
            ],
            delay_seconds=progress_delay_seconds,
        )
        return await build_trend_scout_preview(prompt)
    if task.agent_id == "research_agent":
        await _emit_stages(
            progress,
            [
                "[1/5] 요청을 분석하고 리서치 질문과 출력 목적을 파악합니다.",
                "[2/5] 공개 웹 자료와 1차 출처를 찾습니다.",
                "[3/5] 공식 문서, 가격표, 기사, 리포트의 신뢰도를 비교합니다.",
                "[4/5] 확인된 사실과 가정을 분리해 종합합니다.",
                "[5/5] PM이 결정할 항목과 다음 액션을 정리합니다.",
            ],
            delay_seconds=progress_delay_seconds,
        )
        return await run_web_research(prompt, progress=progress)
    if task.agent_id == "script_writer":
        await _emit_stages(
            progress,
            [
                "[1/4] 요청을 분석하고 대본의 톤과 장면 목적을 정리합니다.",
                "[2/4] benchmark 구조를 바탕으로 장면 단위 초안을 만듭니다.",
                "[3/4] Splitter가 TTS와 자막 타임라인을 준비합니다.",
                "[4/4] 장면 길이와 전달 흐름을 검토합니다.",
            ],
            delay_seconds=progress_delay_seconds,
        )
        return await build_script_preview(prompt)
    if task.agent_id == "developer_agent":
        if is_developer_execution_request(prompt):
            await _emit_stages(
                progress,
                [
                    "[1/5] 명시적인 개발 실행 승인 요청을 확인했습니다.",
                    "[2/5] secret, push, reset 금지 규칙을 적용합니다.",
                    "[3/5] repo 작업공간과 테스트 기준을 준비합니다.",
                    "[4/5] 승인된 범위 안에서 파일 수정과 검증을 진행합니다.",
                    "[5/5] 변경 범위, 테스트, 남은 리스크를 정리합니다.",
                ],
                delay_seconds=progress_delay_seconds,
            )
            return await run_developer_execution(
                prompt,
                progress=progress,
            )
        await _emit_stages(
            progress,
            [
                "[1/6] 개발 요청의 목적과 변경 범위를 파악합니다.",
                "[2/6] Research Agent의 배경 조사 필요성을 검토합니다.",
                "[3/6] 바로 개발하지 않고 PM 승인 조건을 정리합니다.",
                "[4/6] 바뀔 파일, 테스트, 롤백 범위를 좁힙니다.",
                "[5/6] ruff, mypy, pytest 검증 계획을 준비합니다.",
                "[6/6] secret 노출, 과한 리팩터링, 누락 테스트를 점검합니다.",
            ],
            delay_seconds=progress_delay_seconds,
        )
        return await build_developer_preview(prompt)
    if task.agent_id == "grok_planner":
        await _emit_stages(
            progress,
            [
                "[1/4] 요청을 분석하고 10-15초 루프 클립 목표를 정리합니다.",
                "[2/4] 첫 프레임과 마지막 프레임이 자연스럽게 이어지도록 설계합니다.",
                "[3/4] 인물, 카메라, 배경 유지 조건을 점검합니다.",
                "[4/4] Grok에 바로 넣을 수 있는 수동 생성 가이드를 작성합니다.",
            ],
            delay_seconds=progress_delay_seconds,
        )
        return build_grok_prompt_preview(prompt)
    if task.agent_id == "composer":
        await _emit_stages(
            progress,
            [
                "[1/4] 사용할 영상, 음성, 자막 흐름을 확인합니다.",
                "[2/4] 세그먼트와 ASS 자막 구조를 준비합니다.",
                "[3/4] 세로 영상 조립을 위한 FFmpeg 명령 계획을 구성합니다.",
                "[4/4] 출력 길이와 승인 기준을 QC 관점에서 확인합니다.",
            ],
            delay_seconds=progress_delay_seconds,
        )
        return await build_mvp_preview(prompt)
    if task.agent_id == "qc_agent":
        await _emit_stages(
            progress,
            [
                "[1/4] 검토할 산출물과 기준을 확인합니다.",
                "[2/4] 길이, 자막, 음성 계획을 평가합니다.",
                "[3/4] 재시도 필요 여부와 수정 위험을 찾습니다.",
                "[4/4] 승인 또는 재작업 결론을 정리합니다.",
            ],
            delay_seconds=progress_delay_seconds,
        )
        return await build_mvp_preview(prompt)

    return (
        f"Unknown agent: {task.agent_id}\n\n"
        f"{render_agent_catalog()}"
    )


def _clean_prompt(prompt: str) -> str:
    return " ".join(prompt.strip().split()) or "untitled short"


async def _emit_stages(
    progress: ProgressSink | None,
    stages: list[str],
    *,
    delay_seconds: float = 0.0,
) -> None:
    if progress is None:
        return
    for stage in stages:
        await progress(stage)
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)


def _is_self_intro_prompt(prompt: str) -> bool:
    normalized = prompt.strip().lower()
    compact = normalized.replace(" ", "")
    return any(
        phrase in normalized or phrase in compact
        for phrase in [
            "introduce yourself",
            "who are you",
            "self intro",
            "자기소개",
            "넌 누구",
            "뭐 하는",
        ]
    )


def _agent_intro(agent_id: str) -> str:
    if agent_id == "research_agent":
        return "\n".join(
            [
                "Research Agent intro:",
                "저는 AI Shorts Pipeline의 리서치 담당 하위 agent입니다.",
                "PM Supervisor 아래에서 공개 웹 자료를 조사하고 근거와 출처를 정리합니다.",
                (
                    "Instagram/YouTube 트렌드 후보 수집은 Trend Scout가 맡고, "
                    "저는 웹 검색, 자료 비교, 리스크 정리, PM 핸드오프를 맡습니다."
                ),
                (
                    "좋은 요청 예: 'AI 영상 생성비용 트렌드 조사해줘', "
                    "'Grok 10초 루프 활용 사례 리서치해줘'."
                ),
            ]
        )
    if agent_id == "developer_agent":
        return "\n".join(
            [
                "Developer Agent intro:",
                "저는 AI Shorts Pipeline의 개발 담당 하위 agent입니다.",
                (
                    "Research Agent와 PM Supervisor가 방향을 정한 뒤에만 구현 계획을 세우고, "
                    "명시적인 승인 후 코드 변경으로 넘어갑니다."
                ),
                "항상 변경 범위, 테스트 계획, secret 노출 여부, 자기검토 결과를 함께 확인합니다.",
                (
                    "좋은 요청 예: '대시보드에 승인 버튼 추가 기획해줘', "
                    "'Telegram 진행 상태 UI 개선 개발해줘'."
                ),
            ]
        )
    return "\n".join(
        [
            f"{agent_id} intro:",
            "저는 AI Shorts Pipeline의 always-on agent 중 하나입니다.",
            (
                "PM Supervisor와 연결되어 요청을 작업 단위로 나누고 "
                "진행 상태와 최종 결론을 Telegram에 남깁니다."
            ),
        ]
    )
