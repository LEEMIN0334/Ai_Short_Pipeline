from decimal import Decimal

import pytest
from ai_shorts.adapters._stub import StubAdapter
from ai_shorts.adapters.base import CostEvent


@pytest.mark.asyncio
async def test_stub_adapter_records_cost() -> None:
    events: list[CostEvent] = []

    async def sink(event: CostEvent) -> None:
        events.append(event)

    adapter = StubAdapter(cost_sink=sink)
    result = await adapter.do_thing("hi")

    assert result == "stub-output:hi"
    assert len(events) == 1
    assert events[0].service == "stub"
    assert events[0].operation == "do_thing"
    assert events[0].usd == Decimal("0.001")
