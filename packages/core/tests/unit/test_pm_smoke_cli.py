import pytest
from ai_shorts.cli.pm_smoke import run


@pytest.mark.asyncio
async def test_pm_smoke_cli_run_echoes_non_ping() -> None:
    result = await run(thread_id="cli_unit", message="hello")

    assert result == "echo: hello"
