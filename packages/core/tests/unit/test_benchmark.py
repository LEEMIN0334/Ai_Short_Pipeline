from datetime import UTC, datetime

from ai_shorts.agents.benchmark import (
    BenchmarkAgent,
    build_default_scenes,
    template_id_for_trend,
)
from ai_shorts.schemas.trend_item import Platform, TrendItem


def _trend() -> TrendItem:
    return TrendItem(
        source_id="video_001",
        platform=Platform.YOUTUBE,
        url="https://example.com/watch?v=1",
        title="AI agent benchmark",
        author="creator",
        view_count=1000,
        like_count=100,
        comment_count=10,
        share_count=3,
        collected_at=datetime(2026, 5, 16, tzinfo=UTC),
        raw={"duration_ms": 45_000},
    )


def test_build_default_scenes_covers_duration() -> None:
    scenes = build_default_scenes(duration_ms=30_000, title="Example")

    assert scenes[0].start_ms == 0
    assert scenes[-1].end_ms == 30_000
    assert all(scene.end_ms > scene.start_ms for scene in scenes)


def test_benchmark_agent_builds_template() -> None:
    trend = _trend()
    template = BenchmarkAgent().build_template(trend)

    assert template.id == template_id_for_trend(trend)
    assert template.category == "ai"
    assert template.duration_ms == 45_000
    assert template.scenes
    assert "AI agent benchmark" in template.copy_button_text
