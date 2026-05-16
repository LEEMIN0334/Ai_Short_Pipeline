import asyncio
from typing import Any, cast

from ai_shorts.orchestration.celery_app import celery_app
from ai_shorts.orchestration.dag import Dag
from ai_shorts.orchestration.run_state import (
    RunStatus,
    create_run_state,
    mark_run_finished,
    mark_run_started,
)


@cast(Any, celery_app.task(name="ai_shorts.run_dag"))  # type: ignore[untyped-decorator]
def run_dag_task(run_id: str, dag_payload: dict[str, object]) -> dict[str, object]:
    return asyncio.run(_run_dag(run_id=run_id, dag_payload=dag_payload))


async def _run_dag(run_id: str, dag_payload: dict[str, object]) -> dict[str, object]:
    dag = Dag.model_validate(dag_payload)
    await create_run_state(run_id=run_id, dag=dag)
    await mark_run_started(run_id=run_id)
    ordered = dag.ordered_tasks()
    result: dict[str, object] = {
        "run_id": run_id,
        "dag_name": dag.name,
        "tasks": [task.id for task in ordered],
    }
    await mark_run_finished(run_id=run_id, status=RunStatus.SUCCEEDED, result=result)
    return result
