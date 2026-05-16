from decimal import Decimal

from ai_shorts.adapters.base import AdapterBase, CostSink


class StubAdapter(AdapterBase):
    service_name = "stub"

    def __init__(self, cost_sink: CostSink | None = None) -> None:
        super().__init__(cost_sink=cost_sink)

    async def do_thing(self, text: str) -> str:
        await self.record_cost(
            operation="do_thing",
            usd=Decimal("0.001"),
            metadata={"input_length": len(text)},
        )
        return f"stub-output:{text}"

    def estimate_cost(self, operation: str, units: int = 1) -> Decimal:
        if operation != "do_thing":
            return Decimal("0")
        return Decimal("0.001") * units
