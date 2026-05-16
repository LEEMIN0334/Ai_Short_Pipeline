import json
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl

from ai_shorts.adapters.base import AdapterBase, CostSink
from ai_shorts.schemas.trend_item import Platform, TrendItem
from ai_shorts.storage.postgres import get_conn


class InstagramAccountStatus(StrEnum):
    ACTIVE = "active"
    COOLDOWN = "cooldown"
    BLOCKED = "blocked"
    DISABLED = "disabled"


class InstagramAccount(BaseModel):
    id: int
    handle: str
    status: InstagramAccountStatus
    session_ref: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class InstagramMediaKind(StrEnum):
    REEL = "reel"
    POST = "post"
    STORY = "story"
    HIGHLIGHT = "highlight"


class InstagramMedia(BaseModel):
    source_id: str
    kind: InstagramMediaKind
    url: HttpUrl
    title: str = ""
    author: str = ""
    view_count: int | None = Field(default=None, ge=0)
    like_count: int | None = Field(default=None, ge=0)
    comment_count: int | None = Field(default=None, ge=0)
    share_count: int | None = Field(default=None, ge=0)
    published_at: datetime | None = None
    raw: dict[str, object] = Field(default_factory=dict)

    def to_trend_item(self, collected_at: datetime | None = None) -> TrendItem:
        return TrendItem(
            source_id=self.source_id,
            platform=Platform.INSTAGRAM,
            url=self.url,
            title=self.title,
            author=self.author,
            view_count=self.view_count,
            like_count=self.like_count,
            comment_count=self.comment_count,
            share_count=self.share_count,
            published_at=self.published_at,
            collected_at=collected_at or datetime.now(UTC),
            raw={"kind": self.kind.value, **self.raw},
        )


class InstagramSessionRequiredError(RuntimeError):
    """Raised when a real Instagram session is needed but unavailable."""


def _metadata_dict(value: Any) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        loaded = json.loads(value)
        if isinstance(loaded, dict):
            return loaded
    return {}


class InstagramFetcher(AdapterBase):
    service_name = "instagram"

    def __init__(self, cost_sink: CostSink | None = None) -> None:
        super().__init__(cost_sink=cost_sink)

    async def acquire_account(self) -> InstagramAccount | None:
        async with get_conn() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, handle, status, session_ref, metadata
                FROM account_pool
                WHERE platform = 'instagram'
                  AND status = 'active'
                  AND (
                    rate_limit_reset_at IS NULL
                    OR rate_limit_reset_at <= NOW()
                  )
                ORDER BY last_checked_at NULLS FIRST, id
                LIMIT 1
                """
            )

        if row is None:
            return None

        return InstagramAccount(
            id=row["id"],
            handle=row["handle"],
            status=InstagramAccountStatus(row["status"]),
            session_ref=row["session_ref"],
            metadata=_metadata_dict(row["metadata"]),
        )

    async def update_account_status(
        self,
        account_id: int,
        status: InstagramAccountStatus,
        metadata: dict[str, object] | None = None,
    ) -> None:
        async with get_conn() as conn:
            await conn.execute(
                """
                UPDATE account_pool
                SET status = $2,
                    metadata = metadata || $3::jsonb,
                    last_checked_at = NOW(),
                    updated_at = NOW()
                WHERE id = $1
                """,
                account_id,
                status.value,
                json.dumps(metadata or {}),
            )

    async def fetch_reel(self, url: str, account: InstagramAccount | None = None) -> InstagramMedia:
        _ = url
        selected_account = account or await self.acquire_account()
        if selected_account is None or selected_account.session_ref is None:
            msg = "Instagram fetch requires an active account with session_ref"
            raise InstagramSessionRequiredError(msg)

        await self.record_cost(
            operation="fetch_reel",
            usd=Decimal("0"),
            metadata={"account_id": selected_account.id},
        )
        msg = "Real Instagram network fetching is not implemented in Phase 1.1 foundation"
        raise InstagramSessionRequiredError(msg)

    def estimate_cost(self, operation: str, units: int = 1) -> Decimal:
        if operation.startswith("fetch_"):
            return Decimal("0") * units
        return Decimal("0")
