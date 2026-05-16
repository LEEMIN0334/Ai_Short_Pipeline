from collections.abc import Callable, Coroutine
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class CostEvent(BaseModel):
    service: str
    operation: str
    usd: Decimal = Field(ge=0)
    metadata: dict[str, object] = Field(default_factory=dict)


CostSink = Callable[[CostEvent], Coroutine[Any, Any, None]]


class AdapterBase:
    service_name: str

    def __init__(self, cost_sink: CostSink | None = None) -> None:
        self._cost_sink = cost_sink

    async def record_cost(
        self,
        operation: str,
        usd: Decimal,
        metadata: dict[str, object] | None = None,
    ) -> None:
        if self._cost_sink is None:
            return

        event = CostEvent(
            service=self.service_name,
            operation=operation,
            usd=usd,
            metadata=metadata or {},
        )
        await self._cost_sink(event)

    def estimate_cost(self, operation: str, units: int = 1) -> Decimal:
        _ = operation
        _ = units
        return Decimal("0")
