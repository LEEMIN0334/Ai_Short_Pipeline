import json
from hashlib import sha1

from ai_shorts.agents.analyzer import _json_dict, classify_category
from ai_shorts.schemas.benchmark_template import BenchmarkScene, BenchmarkTemplate
from ai_shorts.schemas.trend_item import TrendItem
from ai_shorts.storage.postgres import get_conn


class BenchmarkAgent:
    """Create reusable benchmark templates from collected trend items."""

    def build_template(self, trend: TrendItem) -> BenchmarkTemplate:
        duration_ms = _duration_ms(trend)
        category = classify_category(trend)
        scenes = build_default_scenes(duration_ms=duration_ms, title=trend.title)
        template_id = template_id_for_trend(trend)
        return BenchmarkTemplate(
            id=template_id,
            source_url=trend.url,
            title=trend.title or f"{trend.platform.value}:{trend.source_id}",
            category=category,
            duration_ms=duration_ms,
            scenes=scenes,
            copy_button_text=build_copy_button_text(trend=trend, category=category),
            notes="Phase 1 foundation template generated without multimodal analysis.",
        )

    async def build_and_store(self, trend_item_id: int) -> BenchmarkTemplate:
        async with get_conn() as conn:
            row = await conn.fetchrow(
                """
                SELECT source_id, platform, url, title, author,
                       view_count, like_count, comment_count, share_count,
                       duration_ms, published_at, collected_at, raw
                FROM trend_item
                WHERE id = $1
                """,
                trend_item_id,
            )
            if row is None:
                msg = f"trend_item not found: {trend_item_id}"
                raise ValueError(msg)

            raw = _json_dict(row["raw"])
            if row["duration_ms"] is not None:
                raw["duration_ms"] = row["duration_ms"]

            trend = TrendItem(
                source_id=row["source_id"],
                platform=row["platform"],
                url=row["url"],
                title=row["title"],
                author=row["author"],
                view_count=row["view_count"],
                like_count=row["like_count"],
                comment_count=row["comment_count"],
                share_count=row["share_count"],
                published_at=row["published_at"],
                collected_at=row["collected_at"],
                raw=raw,
            )
            template = self.build_template(trend)
            await conn.execute(
                """
                INSERT INTO benchmark_template (
                    trend_item_id, source_url, title, category,
                    duration_ms, scenes, copy_button_text, notes
                )
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8)
                """,
                trend_item_id,
                str(template.source_url),
                template.title,
                template.category,
                template.duration_ms,
                json.dumps([scene.model_dump() for scene in template.scenes]),
                template.copy_button_text,
                template.notes,
            )

        return template


def build_default_scenes(duration_ms: int, title: str) -> list[BenchmarkScene]:
    safe_duration = max(duration_ms, 3_000)
    scene_count = min(max(round(safe_duration / 10_000), 1), 6)
    segment = safe_duration // scene_count
    scenes: list[BenchmarkScene] = []

    for index in range(scene_count):
        start_ms = index * segment
        end_ms = safe_duration if index == scene_count - 1 else (index + 1) * segment
        scenes.append(
            BenchmarkScene(
                index=index,
                start_ms=start_ms,
                end_ms=end_ms,
                visual_summary=_scene_summary(index=index, title=title),
                hook="opening hook" if index == 0 else None,
                camera_motion="unknown",
                on_screen_text=title if index == 0 and title else None,
            )
        )

    return scenes


def build_copy_button_text(trend: TrendItem, category: str) -> str:
    title = trend.title or "Untitled trend"
    return f"Create a {category} short using the pacing pattern from: {title}"


def template_id_for_trend(trend: TrendItem) -> str:
    digest = sha1(f"{trend.platform}:{trend.source_id}".encode()).hexdigest()[:12]
    return f"tpl_{digest}"


def _duration_ms(trend: TrendItem) -> int:
    raw_duration = trend.raw.get("duration_ms")
    if isinstance(raw_duration, int) and raw_duration > 0:
        return raw_duration
    if isinstance(raw_duration, float) and raw_duration > 0:
        return int(raw_duration)
    return 30_000


def _scene_summary(index: int, title: str) -> str:
    if index == 0:
        return f"Hook viewer with the core promise of '{title or 'the trend'}'."
    return "Continue the pacing pattern with a concise visual beat."
