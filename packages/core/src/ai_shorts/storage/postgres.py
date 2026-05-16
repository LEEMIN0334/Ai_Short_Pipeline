from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg

from ai_shorts.config import get_settings


@asynccontextmanager
async def get_conn() -> AsyncIterator[asyncpg.Connection]:
    """Open a short-lived Postgres connection from POSTGRES_URL."""

    settings = get_settings()
    if not settings.postgres_url:
        msg = "POSTGRES_URL is required to open a Postgres connection"
        raise RuntimeError(msg)

    conn = await asyncpg.connect(settings.postgres_url)
    try:
        yield conn
    finally:
        await conn.close()
