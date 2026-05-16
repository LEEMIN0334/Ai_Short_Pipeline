import pytest
from ai_shorts.adapters.instagram_fetcher import InstagramAccountStatus, InstagramFetcher
from ai_shorts.config import get_settings
from ai_shorts.storage.postgres import get_conn


@pytest.mark.asyncio
async def test_instagram_fetcher_acquires_active_account() -> None:
    if not get_settings().postgres_url:
        pytest.skip("POSTGRES_URL is not configured")

    handle = "phase1_instagram_account"
    fetcher = InstagramFetcher()

    account_id: int | None = None
    try:
        async with get_conn() as conn:
            await conn.execute(
                "DELETE FROM account_pool WHERE platform = 'instagram' AND handle = $1",
                handle,
            )
            account_id = await conn.fetchval(
                """
                INSERT INTO account_pool (platform, handle, status, session_ref, metadata)
                VALUES ('instagram', $1, 'active', 'local-session.json', $2::jsonb)
                RETURNING id
                """,
                handle,
                '{"fixture": true}',
            )

        account = await fetcher.acquire_account()

        await fetcher.update_account_status(
            account_id=account_id,
            status=InstagramAccountStatus.COOLDOWN,
            metadata={"reason": "test"},
        )
        async with get_conn() as conn:
            status_row = await conn.fetchrow(
                "SELECT status, metadata->>'reason' AS reason FROM account_pool WHERE id = $1",
                account_id,
            )
    finally:
        if account_id is not None:
            async with get_conn() as conn:
                await conn.execute("DELETE FROM account_pool WHERE id = $1", account_id)

    assert account is not None
    assert account.handle == handle
    assert account.session_ref == "local-session.json"
    assert status_row is not None
    assert status_row["status"] == "cooldown"
    assert status_row["reason"] == "test"
