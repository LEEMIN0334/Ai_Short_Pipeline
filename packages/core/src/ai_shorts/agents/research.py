import json
import re

from ai_shorts.adapters.research_base import ResearchProvider
from ai_shorts.schemas.research_report import ResearchReport
from ai_shorts.storage.local import LocalStorage
from ai_shorts.storage.postgres import get_conn


class ResearchAgent:
    """Persist research reports from a provider to storage and Postgres."""

    def __init__(self, provider: ResearchProvider, storage: LocalStorage | None = None) -> None:
        self.provider = provider
        self.storage = storage or LocalStorage()

    async def run_and_store(self, query: str) -> ResearchReport:
        report = await self.provider.research(query)
        report_ref = await self.storage.put_bytes(
            key=f"research/{_safe_slug(report.id)}.md",
            data=report.body_markdown.encode("utf-8"),
        )
        await store_research_report(report=report, report_ref=report_ref)
        return report


async def store_research_report(report: ResearchReport, report_ref: str | None = None) -> int:
    async with get_conn() as conn:
        report_id = await conn.fetchval(
            """
            INSERT INTO research_report (title, summary, body_markdown, sources, report_ref)
            VALUES ($1, $2, $3, $4::jsonb, $5)
            RETURNING id
            """,
            report.title,
            report.summary,
            report.body_markdown,
            json.dumps([source.model_dump() for source in report.sources]),
            report_ref,
        )
    return int(report_id)


async def search_research_reports(query: str, limit: int = 10) -> list[dict[str, object]]:
    async with get_conn() as conn:
        rows = await conn.fetch(
            """
            SELECT id, title, summary, report_ref, created_at
            FROM research_report
            WHERE search_vector @@ plainto_tsquery('simple', $1)
            ORDER BY created_at DESC
            LIMIT $2
            """,
            query,
            limit,
        )
    return [dict(row) for row in rows]


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value).strip("-")
    return slug or "report"
