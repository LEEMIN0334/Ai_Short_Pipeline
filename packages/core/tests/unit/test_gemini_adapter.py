import json
from decimal import Decimal

import httpx
import pytest
from ai_shorts.adapters.base import CostEvent
from ai_shorts.adapters.gemini import GeminiAdapter


@pytest.mark.asyncio
async def test_gemini_adapter_requires_api_key() -> None:
    adapter = GeminiAdapter(api_key="", model="gemini-2.0-flash")

    with pytest.raises(RuntimeError, match="Missing GEMINI_API_KEY"):
        await adapter.generate_text("Write a hook")

    await adapter.aclose()


@pytest.mark.asyncio
async def test_gemini_adapter_sends_generate_content_request_and_records_cost() -> None:
    events: list[CostEvent] = []

    async def sink(event: CostEvent) -> None:
        events.append(event)

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.url.path == "/v1beta/models/gemini-2.0-flash:generateContent"
        assert request.headers["x-goog-api-key"] == "test-key"
        assert payload == {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": "Write a short opener"}],
                }
            ],
            "systemInstruction": {
                "parts": [{"text": "You write short-form video scripts."}],
            },
            "generationConfig": {"temperature": 0.4},
        }
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": "Open with "},
                                {"text": "the result first."},
                            ],
                            "role": "model",
                        },
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 12,
                    "candidatesTokenCount": 7,
                },
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = GeminiAdapter(
        api_key="test-key",
        model="gemini-2.0-flash",
        client=client,
        cost_sink=sink,
        estimated_unit_usd=Decimal("0.02"),
    )

    result = await adapter.generate_text(
        "Write a short opener",
        system_instruction="You write short-form video scripts.",
        generation_config={"temperature": 0.4},
        metadata={"job_id": "phase2_001"},
    )

    assert result.text == "Open with the result first."
    assert result.model == "gemini-2.0-flash"
    assert result.usage_metadata == {
        "promptTokenCount": 12,
        "candidatesTokenCount": 7,
    }
    assert len(events) == 1
    assert events[0].service == "gemini"
    assert events[0].operation == "generateContent"
    assert events[0].usd == Decimal("0.02")
    assert events[0].metadata["model"] == "gemini-2.0-flash"
    assert events[0].metadata["job_id"] == "phase2_001"
    await client.aclose()


@pytest.mark.asyncio
async def test_gemini_adapter_supports_model_resource_names() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models/gemini-3-flash-preview:generateContent"
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "ok"}]}}]},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = GeminiAdapter(
        api_key="test-key",
        model="models/gemini-3-flash-preview",
        api_version="v1",
        client=client,
    )

    result = await adapter.generate_text("Hello")

    assert result.text == "ok"
    await client.aclose()


@pytest.mark.asyncio
async def test_gemini_adapter_raises_for_http_errors() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="rate limit")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = GeminiAdapter(api_key="test-key", client=client)

    with pytest.raises(RuntimeError, match="Gemini request failed: 429 rate limit"):
        await adapter.generate_text("Hello")

    await client.aclose()


@pytest.mark.asyncio
async def test_gemini_adapter_raises_for_missing_text() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"candidates": [{"content": {"parts": []}}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = GeminiAdapter(api_key="test-key", client=client)

    with pytest.raises(RuntimeError, match="Gemini response did not include text"):
        await adapter.generate_text("Hello")

    await client.aclose()


def test_gemini_adapter_estimates_generate_content_cost() -> None:
    adapter = GeminiAdapter(
        api_key="test-key",
        estimated_unit_usd=Decimal("0.03"),
    )

    assert adapter.estimate_cost("generateContent", units=4) == Decimal("0.12")
    assert adapter.estimate_cost("unknown", units=4) == Decimal("0")
