import json
from decimal import Decimal

import httpx
import pytest
from ai_shorts.adapters.base import CostEvent
from ai_shorts.adapters.typecast import TypecastAdapter


@pytest.mark.asyncio
async def test_typecast_adapter_requires_api_key() -> None:
    adapter = TypecastAdapter(api_key="", voice_id="tc_voice")

    with pytest.raises(RuntimeError, match="Missing TYPECAST_API_KEY"):
        await adapter.synthesize("안녕하세요")

    await adapter.aclose()


@pytest.mark.asyncio
async def test_typecast_adapter_requires_voice_id() -> None:
    adapter = TypecastAdapter(api_key="test-key", voice_id="")

    with pytest.raises(RuntimeError, match="Missing TYPECAST_VOICE_ID"):
        await adapter.synthesize("안녕하세요")

    await adapter.aclose()


@pytest.mark.asyncio
async def test_typecast_adapter_sends_tts_request_and_records_cost() -> None:
    events: list[CostEvent] = []

    async def sink(event: CostEvent) -> None:
        events.append(event)

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.url.path == "/v1/text-to-speech"
        assert request.headers["X-API-KEY"] == "test-key"
        assert payload == {
            "voice_id": "tc_voice",
            "text": "짧은 영상 오프닝입니다.",
            "model": "ssfm-v30",
            "language": "kor",
            "prompt": {"emotion_type": "smart"},
            "output": {
                "volume": 92,
                "audio_pitch": 1,
                "audio_tempo": 1.05,
                "audio_format": "wav",
            },
            "seed": 42,
        }
        return httpx.Response(
            200,
            content=b"RIFF....WAVE",
            headers={"content-type": "audio/wav"},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TypecastAdapter(
        api_key="test-key",
        voice_id="tc_voice",
        model="ssfm-v30",
        client=client,
        cost_sink=sink,
        estimated_unit_usd=Decimal("0.05"),
    )

    result = await adapter.synthesize(
        "짧은 영상 오프닝입니다.",
        prompt={"emotion_type": "smart"},
        volume=92,
        audio_pitch=1,
        audio_tempo=1.05,
        seed=42,
        metadata={"job_id": "phase2_003"},
    )

    assert result.audio_bytes == b"RIFF....WAVE"
    assert result.content_type == "audio/wav"
    assert result.voice_id == "tc_voice"
    assert result.model == "ssfm-v30"
    assert result.language == "kor"
    assert len(events) == 1
    assert events[0].service == "typecast"
    assert events[0].operation == "text-to-speech"
    assert events[0].usd == Decimal("0.05")
    assert events[0].metadata["job_id"] == "phase2_003"
    assert events[0].metadata["billable_units"] == 1
    await client.aclose()


@pytest.mark.asyncio
async def test_typecast_adapter_allows_per_call_voice_and_language_override() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["voice_id"] == "tc_other"
        assert payload["language"] == "eng"
        assert payload["output"]["audio_format"] == "mp3"
        return httpx.Response(200, content=b"MP3", headers={"content-type": "audio/mpeg"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TypecastAdapter(api_key="test-key", voice_id="tc_default", client=client)

    result = await adapter.synthesize(
        "Everything is perfect.",
        voice_id="tc_other",
        language="eng",
        audio_format="mp3",
    )

    assert result.audio_bytes == b"MP3"
    assert result.audio_format == "mp3"
    assert result.content_type == "audio/mpeg"
    await client.aclose()


@pytest.mark.asyncio
async def test_typecast_adapter_raises_for_http_errors() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorized")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TypecastAdapter(api_key="test-key", voice_id="tc_voice", client=client)

    with pytest.raises(RuntimeError, match="Typecast request failed: 401 unauthorized"):
        await adapter.synthesize("안녕하세요")

    await client.aclose()


@pytest.mark.asyncio
async def test_typecast_adapter_raises_for_empty_audio() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TypecastAdapter(api_key="test-key", voice_id="tc_voice", client=client)

    with pytest.raises(RuntimeError, match="Typecast response did not include audio bytes"):
        await adapter.synthesize("안녕하세요")

    await client.aclose()


@pytest.mark.asyncio
async def test_typecast_adapter_validates_text_length() -> None:
    adapter = TypecastAdapter(api_key="test-key", voice_id="tc_voice")

    with pytest.raises(RuntimeError, match="Typecast text must not be empty"):
        await adapter.synthesize("   ")

    with pytest.raises(RuntimeError, match="Typecast text must be 2000 characters or fewer"):
        await adapter.synthesize("a" * 2001)

    await adapter.aclose()


def test_typecast_adapter_estimates_tts_cost() -> None:
    adapter = TypecastAdapter(
        api_key="test-key",
        voice_id="tc_voice",
        estimated_unit_usd=Decimal("0.03"),
    )

    assert adapter.estimate_cost("text-to-speech", units=4) == Decimal("0.12")
    assert adapter.estimate_cost("synthesize", units=2) == Decimal("0.06")
    assert adapter.estimate_cost("unknown", units=4) == Decimal("0")
