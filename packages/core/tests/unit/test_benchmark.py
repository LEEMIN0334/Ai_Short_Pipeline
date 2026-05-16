from datetime import UTC, datetime

import pytest
from ai_shorts.agents.benchmark import (
    BenchmarkPolicy,
    build_benchmark_template,
    build_benchmark_templates,
)
from ai_shorts.schemas.trend_item import Platform, ScoredTrendItem, TrendItem
from pydantic import ValidationError


def _scored(
    source_id: str,
    *,
    score: float = 42.5,
    title: str = "Three-second pasta hook",
    category: str = "food",
    platform: Platform = Platform.INSTAGRAM,
    views: int = 12000,
    raw: dict[str, object] | None = None,
) -> ScoredTrendItem:
    return ScoredTrendItem(
        trend=TrendItem(
            source_id=source_id,
            platform=platform,
            url=f"https://example.com/reel/{source_id}",
            title=title,
            view_count=views,
            like_count=900,
            comment_count=80,
            collected_at=datetime(2026, 5, 16, tzinfo=UTC),
            raw=raw or {},
        ),
        viral_score=score,
        category=category,
        reasons=["reach=12000", f"platform={platform.value}"],
    )


def test_build_benchmark_template_uses_scored_trend_metadata() -> None:
    candidate = _scored(
        "ig_001",
        raw={
            "duration_ms": 32000,
            "hook": "This pasta trick takes three seconds",
            "copy_button_text": "Copy the pasta hook",
        },
    )

    template = build_benchmark_template(candidate)

    assert template.id == "benchmark-01-instagram-ig-001"
    assert str(template.source_url) == "https://example.com/reel/ig_001"
    assert template.title == "Three-second pasta hook Benchmark"
    assert template.category == "food"
    assert template.duration_ms == 32000
    assert len(template.scenes) == 4
    assert template.scenes[0].hook == "This pasta trick takes three seconds"
    assert template.scenes[-1].on_screen_text == "Copy the pasta hook"
    assert "viral_score=42.5" in template.notes


def test_build_benchmark_templates_limits_candidates_and_preserves_rank() -> None:
    candidates = [
        _scored("first", score=50),
        _scored("second", score=40),
        _scored("third", score=30),
    ]
    policy = BenchmarkPolicy(max_templates=2)

    templates = build_benchmark_templates(candidates, policy=policy)

    assert [template.id for template in templates] == [
        "benchmark-01-instagram-first",
        "benchmark-02-instagram-second",
    ]


def test_benchmark_policy_clamps_duration_and_scene_spans() -> None:
    candidate = _scored("long", raw={"duration_ms": 999999})
    policy = BenchmarkPolicy(max_duration_ms=60000, scene_count=3)

    template = build_benchmark_template(candidate, policy=policy)

    assert template.duration_ms == 60000
    assert [(scene.start_ms, scene.end_ms) for scene in template.scenes] == [
        (0, 20000),
        (20000, 40000),
        (40000, 60000),
    ]


def test_benchmark_policy_rejects_invalid_duration_bounds() -> None:
    with pytest.raises(ValidationError, match="min_duration_ms"):
        BenchmarkPolicy(
            default_duration_ms=45000,
            min_duration_ms=60000,
            max_duration_ms=15000,
        )
