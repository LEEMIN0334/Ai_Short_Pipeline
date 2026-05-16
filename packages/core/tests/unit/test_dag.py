import pytest
from ai_shorts.orchestration.dag import Dag, DagTask, DagTaskKind, build_collection_dag


def test_build_collection_dag_orders_tasks() -> None:
    dag = build_collection_dag(run_id="run_001", query="ai shorts")

    assert [task.kind for task in dag.ordered_tasks()] == [
        DagTaskKind.TREND_SCOUT,
        DagTaskKind.ANALYZER,
        DagTaskKind.BENCHMARK,
    ]


def test_dag_rejects_missing_dependency() -> None:
    with pytest.raises(ValueError):
        Dag(
            name="bad",
            tasks=[
                DagTask(
                    id="analyzer",
                    kind=DagTaskKind.ANALYZER,
                    depends_on=["missing"],
                )
            ],
        )


def test_dag_rejects_cycle() -> None:
    with pytest.raises(ValueError):
        Dag(
            name="cycle",
            tasks=[
                DagTask(id="a", kind=DagTaskKind.ANALYZER, depends_on=["b"]),
                DagTask(id="b", kind=DagTaskKind.BENCHMARK, depends_on=["a"]),
            ],
        )
