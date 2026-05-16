import pytest
from ai_shorts.config import get_settings
from ai_shorts.orchestration.dag import build_collection_dag
from ai_shorts.orchestration.run_state import (
    RunStatus,
    create_run_state,
    get_run_state,
    mark_run_finished,
    mark_run_started,
)
from ai_shorts.storage.postgres import get_conn


@pytest.mark.asyncio
async def test_run_state_lifecycle() -> None:
    if not get_settings().postgres_url:
        pytest.skip("POSTGRES_URL is not configured")

    run_id = "phase1_run_state_001"
    dag = build_collection_dag(run_id=run_id, query="ai shorts")

    try:
        await create_run_state(run_id=run_id, dag=dag)
        await mark_run_started(run_id=run_id, current_task=dag.ordered_tasks()[0].id)
        await mark_run_finished(
            run_id=run_id,
            status=RunStatus.SUCCEEDED,
            result={"ok": True},
        )

        state = await get_run_state(run_id)

        assert state is not None
        assert state["status"] == "succeeded"
        assert state["current_task"] == dag.ordered_tasks()[0].id
    finally:
        async with get_conn() as conn:
            await conn.execute("DELETE FROM run_state WHERE run_id = $1", run_id)
