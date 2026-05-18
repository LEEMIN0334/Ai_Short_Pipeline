import json
from decimal import Decimal

import httpx
import pytest
from ai_shorts.adapters.typecast import TypecastAdapter
from ai_shorts.agents.voiceover import VoiceoverPolicy, synthesize_voiceovers
from ai_shorts.observability.cost_guard import CostGuardPolicy, CostGuardStatus
from ai_shorts.schemas.script import ScriptSegment, ScriptSplit
from ai_shorts.storage.local import LocalStorage


def _split() -> ScriptSplit:
    return ScriptSplit(
        script_id="script-01",
        language="ko",
        target_duration_ms=5000,
        segments=[
            ScriptSegment(
                segment_id="segment-script-01-s00-l00-c00",
                script_id="script-01",
                scene_index=0,
                line_index=0,
                chunk_index=0,
                speaker="narrator",
                text="첫 장면은 결과부터 보여줍니다.",
                start_ms=0,
                end_ms=2500,
            ),
            ScriptSegment(
                segment_id="segment-script-01-s01-l00-c00",
                script_id="script-01",
                scene_index=1,
                line_index=0,
                chunk_index=0,
                speaker="narrator",
                text="두 번째 장면은 따라 할 이유를 설명합니다.",
                start_ms=2500,
                end_ms=5000,
            ),
        ],
    )


@pytest.mark.asyncio
async def test_synthesize_voiceovers_blocks_without_confirmation(tmp_path) -> None:
    adapter = TypecastAdapter(
        api_key="test-key",
        voice_id="tc_voice",
        estimated_unit_usd=Decimal("0.20"),
    )

    result = await synthesize_voiceovers(
        _split(),
        adapter=adapter,
        storage=LocalStorage(root=tmp_path),
        cost_guard_policy=CostGuardPolicy(
            auto_approve_limit_usd=Decimal("0.05"),
            hard_limit_usd=Decimal("1.00"),
            confirmation_phrase="APPROVE_TTS",
        ),
    )

    assert result.used_typecast is False
    assert result.assets == []
    assert result.cost_guard.status == CostGuardStatus.REQUIRES_CONFIRMATION
    assert result.cost_guard.total_usd == Decimal("0.40")
    assert not any(tmp_path.rglob("*"))
    await adapter.aclose()


@pytest.mark.asyncio
async def test_synthesize_voiceovers_stores_audio_assets(tmp_path) -> None:
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            content=f"audio-{len(requests)}".encode(),
            headers={"content-type": "audio/wav"},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TypecastAdapter(
        api_key="test-key",
        voice_id="tc_voice",
        client=client,
        estimated_unit_usd=Decimal("0.01"),
    )

    result = await synthesize_voiceovers(
        _split(),
        adapter=adapter,
        storage=LocalStorage(root=tmp_path),
        policy=VoiceoverPolicy(prompt={"emotion_type": "smart"}, volume=90),
    )

    assert result.used_typecast is True
    assert result.cost_guard.status == CostGuardStatus.APPROVED
    assert len(result.assets) == 2
    assert requests[0]["text"] == "첫 장면은 결과부터 보여줍니다."
    assert requests[0]["prompt"] == {"emotion_type": "smart"}
    assert requests[0]["output"]["volume"] == 90
    assert result.assets[0].media.mime_type == "audio/wav"
    assert result.assets[0].media.duration_ms == 2500
    assert result.assets[0].media.uri.endswith("segment-script-01-s00-l00-c00.wav")
    assert (tmp_path / "voiceovers/script-01/segment-script-01-s00-l00-c00.wav").read_bytes() == (
        b"audio-1"
    )
    assert (tmp_path / "voiceovers/script-01/segment-script-01-s01-l00-c00.wav").read_bytes() == (
        b"audio-2"
    )
    await client.aclose()
