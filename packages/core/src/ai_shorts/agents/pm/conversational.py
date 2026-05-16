from ai_shorts.adapters._stub import StubAdapter
from ai_shorts.observability.cost_log import make_postgres_sink


async def handle_message(thread_id: str, user_text: str) -> str:
    """Phase 0 PM smoke handler."""

    sink = make_postgres_sink(job_id=thread_id, agent_id="pm")
    stub = StubAdapter(cost_sink=sink)
    normalized = user_text.strip().lower()

    if normalized == "ping":
        result = await stub.do_thing("ping")
        return f"pong (via {result})"

    return f"echo: {user_text}"
