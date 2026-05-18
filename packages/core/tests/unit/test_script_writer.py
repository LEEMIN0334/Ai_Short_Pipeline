import json
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest
from ai_shorts.adapters.gemini import GeminiAdapter
from ai_shorts.agents.script_writer import (
    ScriptWriterPolicy,
    write_script_from_benchmark,
    write_script_with_gemini,
    write_scripts_for_package,
)
from ai_shorts.observability.cost_guard import CostGuardPolicy, CostGuardStatus
from ai_shorts.schemas.benchmark_template import BenchmarkScene, BenchmarkTemplate
from ai_shorts.schemas.research_report import ResearchReport


def _benchmark() -> BenchmarkTemplate:
    return BenchmarkTemplate(
        id="benchmark-01-instagram-ig-top",
        source_url="https://example.com/reel/ig-top",
        title="Three-second pasta reveal Benchmark",
        category="food",
        duration_ms=30000,
        copy_button_text="Copy the reveal structure",
        scenes=[
            BenchmarkScene(
                index=0,
                start_ms=0,
                end_ms=8000,
                visual_summary="Open on the finished pasta reveal.",
                hook="This pasta reveal takes three seconds",
                camera_motion="fast push-in",
                on_screen_text="3-second reveal",
            ),
            BenchmarkScene(
                index=1,
                start_ms=8000,
                end_ms=18000,
                visual_summary="Show why the setup works.",
                camera_motion="quick proof cuts",
                on_screen_text="Food signal",
            ),
            BenchmarkScene(
                index=2,
                start_ms=18000,
                end_ms=30000,
                visual_summary="Loop back to the first frame.",
                camera_motion="match cut",
                on_screen_text="Copy the reveal structure",
            ),
        ],
    )


def _research_report() -> ResearchReport:
    return ResearchReport(
        id="trend-research-20260516120000",
        title="Food Trend Brief",
        summary="2 curated trend(s) found. Top candidate ig_top scored 42.0.",
        body_markdown="## Report",
        created_at=datetime(2026, 5, 16, tzinfo=UTC),
    )


def test_write_script_from_benchmark_preserves_template_timing() -> None:
    script = write_script_from_benchmark(
        _benchmark(),
        research_report=_research_report(),
    )

    assert script.id == "script-benchmark-01-instagram-ig-top"
    assert script.template_id == "benchmark-01-instagram-ig-top"
    assert script.title == "Three-second pasta reveal Script"
    assert script.target_duration_ms == 30000
    assert script.language == "ko"
    assert [scene.index for scene in script.scenes] == [0, 1, 2]
    assert [(line.start_ms, line.end_ms) for scene in script.scenes for line in scene.lines] == [
        (0, 8000),
        (8000, 18000),
        (18000, 30000),
    ]


def test_write_script_from_benchmark_uses_hook_and_research_summary() -> None:
    script = write_script_from_benchmark(
        _benchmark(),
        research_report=_research_report(),
    )

    assert script.scenes[0].lines[0].text == "This pasta reveal takes three seconds"
    assert script.scenes[0].lines[0].emphasis_cue == "hook"
    assert script.scenes[1].lines[0].text == (
        "2 curated trend(s) found. Top candidate ig_top scored 42.0."
    )
    assert "Camera: quick proof cuts." in script.scenes[1].visual_prompt
    assert "Format reference: https://example.com/reel/ig-top." in script.scenes[1].visual_prompt


def test_write_script_from_benchmark_truncates_long_lines() -> None:
    benchmark = _benchmark()
    benchmark.scenes[0].hook = " ".join(["verylonghook"] * 12)
    policy = ScriptWriterPolicy(max_line_chars=40)

    script = write_script_from_benchmark(benchmark, policy=policy)

    assert len(script.scenes[0].lines[0].text) <= 40
    assert script.scenes[0].lines[0].text.endswith("...")


def test_write_scripts_for_package_creates_one_script_per_benchmark() -> None:
    scripts = write_scripts_for_package(
        [_benchmark(), _benchmark().model_copy(update={"id": "benchmark-02-youtube-yt"})],
        research_report=_research_report(),
    )

    assert [script.id for script in scripts] == [
        "script-benchmark-01-instagram-ig-top",
        "script-benchmark-02-youtube-yt",
    ]


@pytest.mark.asyncio
async def test_write_script_with_gemini_blocks_without_confirmation() -> None:
    adapter = GeminiAdapter(
        api_key="test-key",
        estimated_unit_usd=Decimal("0.50"),
    )

    result = await write_script_with_gemini(
        _benchmark(),
        research_report=_research_report(),
        adapter=adapter,
        cost_guard_policy=CostGuardPolicy(
            auto_approve_limit_usd=Decimal("0.05"),
            hard_limit_usd=Decimal("1.00"),
            confirmation_phrase="APPROVE_GEMINI_SCRIPT",
        ),
    )

    assert result.used_gemini is False
    assert result.cost_guard.status == CostGuardStatus.REQUIRES_CONFIRMATION
    assert result.cost_guard.confirmation_phrase == "APPROVE_GEMINI_SCRIPT"
    assert result.script.scenes[0].lines[0].text == "This pasta reveal takes three seconds"
    await adapter.aclose()


@pytest.mark.asyncio
async def test_write_script_with_gemini_uses_approved_adapter_response() -> None:
    events: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        events.append(payload)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "title": "Gemini Pasta Loop Script",
                                            "scenes": [
                                                {
                                                    "index": 0,
                                                    "line": (
                                                        "완성된 파스타부터 보여주고 "
                                                        "바로 이유를 말해요."
                                                    ),
                                                    "emphasis_cue": "hook",
                                                },
                                                {
                                                    "index": 1,
                                                    "line": (
                                                        "세팅이 쉬워서 누구나 같은 "
                                                        "장면을 따라할 수 있어요."
                                                    ),
                                                },
                                            ],
                                        },
                                        ensure_ascii=False,
                                    )
                                }
                            ]
                        }
                    }
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = GeminiAdapter(
        api_key="test-key",
        model="gemini-2.0-flash",
        client=client,
        estimated_unit_usd=Decimal("0.01"),
    )

    result = await write_script_with_gemini(
        _benchmark(),
        research_report=_research_report(),
        adapter=adapter,
    )

    assert result.used_gemini is True
    assert result.cost_guard.status == CostGuardStatus.APPROVED
    assert result.script.title == "Gemini Pasta Loop Script"
    assert result.script.scenes[0].lines[0].text == "완성된 파스타부터 보여주고 바로 이유를 말해요."
    assert result.script.scenes[1].lines[0].text == (
        "세팅이 쉬워서 누구나 같은 장면을 따라할 수 있어요."
    )
    assert result.script.scenes[2].lines[0].text == (
        "This is the repeatable structure: Copy the reveal structure."
    )
    assert events[0]["generationConfig"] == {
        "temperature": 0.7,
        "response_mime_type": "application/json",
    }
    await client.aclose()
