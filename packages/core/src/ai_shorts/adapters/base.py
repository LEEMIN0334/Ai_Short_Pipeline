from collections.abc import Awaitable
from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel, Field


class CostEvent(BaseModel):
    service: str
    operation: str
    usd: Decimal = Field(ge=0)
    metadata: dict[str, object] = Field(default_factory=dict)


class CostSink(Protocol):
    def __call__(self, event: CostEvent) -> Awaitable[None]:
        ...


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
