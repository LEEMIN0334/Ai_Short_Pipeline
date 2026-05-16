from datetime import UTC, datetime

from ai_shorts.agents.script_writer import (
    ScriptWriterPolicy,
    write_script_from_benchmark,
    write_scripts_for_package,
)
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
