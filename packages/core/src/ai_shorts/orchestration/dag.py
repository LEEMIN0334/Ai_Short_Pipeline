from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class DagTaskKind(StrEnum):
    TREND_SCOUT = "trend_scout"
    ANALYZER = "analyzer"
    BENCHMARK = "benchmark"
    RESEARCH = "research"


class DagTask(BaseModel):
    id: str
    kind: DagTaskKind
    depends_on: list[str] = Field(default_factory=list)
    params: dict[str, object] = Field(default_factory=dict)


class Dag(BaseModel):
    name: str
    tasks: list[DagTask]

    @model_validator(mode="after")
    def validate_graph(self) -> "Dag":
        task_ids = [task.id for task in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            msg = "DAG task ids must be unique"
            raise ValueError(msg)

        known_ids = set(task_ids)
        for task in self.tasks:
            missing = [dep for dep in task.depends_on if dep not in known_ids]
            if missing:
                msg = f"Task {task.id} depends on missing tasks: {missing}"
                raise ValueError(msg)

        _topological_order(self.tasks)
        return self

    def ordered_tasks(self) -> list[DagTask]:
        return _topological_order(self.tasks)


def build_collection_dag(run_id: str, query: str) -> Dag:
    return Dag(
        name="phase1_collection",
        tasks=[
            DagTask(
                id=f"{run_id}:trend_scout",
                kind=DagTaskKind.TREND_SCOUT,
                params={"query": query},
            ),
            DagTask(
                id=f"{run_id}:analyzer",
                kind=DagTaskKind.ANALYZER,
                depends_on=[f"{run_id}:trend_scout"],
            ),
            DagTask(
                id=f"{run_id}:benchmark",
                kind=DagTaskKind.BENCHMARK,
                depends_on=[f"{run_id}:analyzer"],
            ),
        ],
    )


def _topological_order(tasks: list[DagTask]) -> list[DagTask]:
    by_id = {task.id: task for task in tasks}
    temporary: set[str] = set()
    permanent: set[str] = set()
    ordered: list[DagTask] = []

    def visit(task: DagTask) -> None:
        if task.id in permanent:
            return
        if task.id in temporary:
            msg = f"DAG contains a cycle at task {task.id}"
            raise ValueError(msg)

        temporary.add(task.id)
        for dep_id in task.depends_on:
            visit(by_id[dep_id])
        temporary.remove(task.id)
        permanent.add(task.id)
        ordered.append(task)

    for task in tasks:
        visit(task)

    return ordered
