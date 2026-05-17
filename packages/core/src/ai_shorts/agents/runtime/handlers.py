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
    build_research_preview,
    build_script_preview,
)
from ai_shorts.agents.runtime.registry import render_agent_catalog
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
                "[1/3] 요청 확인 중: 자기소개 요청으로 인식했습니다.",
                "[2/3] 역할 정리 중: agent의 담당 범위와 PM 연결 방식을 확인합니다.",
                "[3/3] 응답 작성 중: 사용자가 바로 이해할 수 있게 짧게 정리합니다.",
            ],
            delay_seconds=progress_delay_seconds,
        )
        return _agent_intro(task.agent_id)

    if task.agent_id == "pm_supervisor":
        await _emit_stages(
            progress,
            [
                "[1/5] 요청 분석 중: PM이 목표와 필요한 하위 agent를 정리합니다.",
                "[2/5] 리서치 준비 중: Trend Scout와 Research Agent 작업 범위를 잡습니다.",
                "[3/5] 대본 구성 중: Script Writer와 Splitter가 장면 구조를 만듭니다.",
                "[4/5] 조립 계획 중: Composer가 자막, 음성, 영상 결합 계획을 확인합니다.",
                "[5/5] 최종 검수 중: QC Agent가 승인/재시도 게이트를 점검합니다.",
            ],
            delay_seconds=progress_delay_seconds,
        )
        return await build_mvp_preview(prompt)
    if task.agent_id == "trend_scout":
        await _emit_stages(
            progress,
            [
                "[1/4] 요청 분석 중: 트렌드 후보를 찾을 주제를 정리합니다.",
                "[2/4] 소스 스캔 중: 현재 로컬 preview 신호를 수집합니다.",
                "[3/4] 후보 점수화 중: 조회수, 반응, 신선도를 비교합니다.",
                "[4/4] 중복 제거 중: Research Agent에 넘길 후보만 남깁니다.",
            ],
            delay_seconds=progress_delay_seconds,
        )
        return await build_research_preview(prompt)
    if task.agent_id == "research_agent":
        await _emit_stages(
            progress,
            [
                "[1/5] 요청 분석 중: 리서치 질문과 출력 목적을 파악합니다.",
                (
                    "[2/5] 소스 확인 중: 현재 로컬 preview 모드에서 "
                    "Instagram/YouTube 신호를 확인합니다."
                ),
                "[3/5] 리서치 패키지 작성 중: 핵심 요약과 생성 가능성을 정리합니다.",
                "[4/5] 벤치마크 구성 중: 숏츠 제작에 쓸 템플릿을 만듭니다.",
                "[5/5] 최종 검토 중: PM에게 넘길 수 있는 상태인지 확인합니다.",
            ],
            delay_seconds=progress_delay_seconds,
        )
        return await build_research_preview(prompt)
    if task.agent_id == "script_writer":
        await _emit_stages(
            progress,
            [
                "[1/4] 요청 분석 중: 대본의 훅과 장면 목적을 정리합니다.",
                "[2/4] 대본 작성 중: Script Writer가 짧은 장면 단위로 초안을 만듭니다.",
                "[3/4] 세그먼트 분리 중: Splitter가 TTS/자막 타이밍을 준비합니다.",
                "[4/4] 최종 검토 중: 장면 길이와 전달 흐름을 확인합니다.",
            ],
            delay_seconds=progress_delay_seconds,
        )
        return await build_script_preview(prompt)
    if task.agent_id == "developer_agent":
        if is_developer_execution_request(prompt):
            await _emit_stages(
                progress,
                [
                    "[1/5] 실행 승인 확인 중: 명시적인 개발 실행 요청을 확인했습니다.",
                    "[2/5] 안전 게이트 확인 중: secret, push, reset 금지 규칙을 적용합니다.",
                    "[3/5] Codex 실행 준비 중: repo 작업공간과 테스트 기준을 설정합니다.",
                    "[4/5] 실제 개발 실행 중: 파일 수정과 검증을 진행합니다.",
                    "[5/5] 자기검수 중: 변경 범위, 테스트, 잔여 리스크를 정리합니다.",
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
                "[1/6] 요청 분석 중: 개발 요청의 목적과 변경 범위를 파악합니다.",
                "[2/6] 리서치 확인 중: Research Agent의 배경 조사와 리스크를 먼저 검토합니다.",
                "[3/6] PM 게이트 확인 중: 바로 개발하지 않고 승인 조건을 정리합니다.",
                "[4/6] 구현 계획 중: 바꿀 파일, 테스트, 롤백 범위를 좁힙니다.",
                "[5/6] 검증 계획 중: ruff, mypy, pytest와 수동 확인 포인트를 세웁니다.",
                "[6/6] 자기검수 중: secret 유출, 과한 리팩터링, 누락 테스트를 확인합니다.",
            ],
            delay_seconds=progress_delay_seconds,
        )
        return await build_developer_preview(prompt)
    if task.agent_id == "grok_planner":
        await _emit_stages(
            progress,
            [
                "[1/4] 요청 분석 중: 10-15초 루프형 클립 목표를 정리합니다.",
                "[2/4] 프롬프트 구성 중: 첫 프레임과 마지막 프레임이 맞도록 설계합니다.",
                "[3/4] 일관성 점검 중: 인물, 카메라, 배경 유지 조건을 확인합니다.",
                "[4/4] 수동 생성 가이드 작성 중: Grok에서 바로 넣을 문장을 준비합니다.",
            ],
            delay_seconds=progress_delay_seconds,
        )
        return build_grok_prompt_preview(prompt)
    if task.agent_id == "composer":
        await _emit_stages(
            progress,
            [
                "[1/4] 요청 분석 중: 사용할 영상/음성/자막 흐름을 확인합니다.",
                "[2/4] 자막 계획 중: 세그먼트와 ASS 자막 구조를 준비합니다.",
                "[3/4] FFmpeg 계획 중: 세로 영상 조립 명령을 구성합니다.",
                "[4/4] QC 확인 중: 출력 길이와 승인 게이트를 점검합니다.",
            ],
            delay_seconds=progress_delay_seconds,
        )
        return await build_mvp_preview(prompt)
    if task.agent_id == "qc_agent":
        await _emit_stages(
            progress,
            [
                "[1/4] 요청 분석 중: 검수할 산출물과 기준을 확인합니다.",
                "[2/4] 품질 확인 중: 길이, 자막, 음성 계획을 점검합니다.",
                "[3/4] 재시도 판단 중: 수정이 필요한 위험을 찾습니다.",
                "[4/4] 결론 작성 중: 승인 또는 재작업 결정을 정리합니다.",
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
            "너누구",
            "뭐하는",
        ]
    )


def _agent_intro(agent_id: str) -> str:
    if agent_id == "research_agent":
        return "\n".join(
            [
                "Research Agent intro:",
                "나는 AI Shorts Pipeline의 리서치 담당 하위 agent입니다.",
                "PM Supervisor 아래에서 트렌드 후보, 참고 소스, 벤치마크 방향을 정리합니다.",
                (
                    "지금 단계에서는 로컬 preview 신호를 기반으로 조사 패키지를 만들고, "
                    "외부 웹/API 리서치는 연결된 뒤 실제 호출 단계만 웹 검색으로 표시합니다."
                ),
                (
                    "좋은 요청 예: 'AI 영상 가성비 플랫폼 조사해줘', "
                    "'Grok 10초 루프 쇼츠 사례 리서치해줘'."
                ),
            ]
        )
    if agent_id == "developer_agent":
        return "\n".join(
            [
                "Developer Agent intro:",
                "나는 AI Shorts Pipeline의 개발 담당 하위 agent입니다.",
                (
                    "Research Agent와 PM Supervisor가 방향을 잡은 뒤에만 구현 계획을 세우고, "
                    "승인 후 코드 변경으로 넘어갑니다."
                ),
                "항상 변경 범위, 테스트 계획, secret 유출 여부, 자기검수 결과를 같이 확인합니다.",
                (
                    "좋은 요청 예: '대시보드에 승인 버튼 추가 기획해줘', "
                    "'Telegram 진행 상태 UI 개선 개발해줘'."
                ),
            ]
        )
    return "\n".join(
        [
            f"{agent_id} intro:",
            "나는 AI Shorts Pipeline의 always-on agent 중 하나입니다.",
            (
                "PM Supervisor와 연결되어 요청을 작업 단위로 나누고, "
                "진행 상태와 최종 결론을 Telegram에 남깁니다."
            ),
        ]
    )
