from decimal import Decimal

import httpx
from pydantic import BaseModel, Field

from ai_shorts.adapters.base import AdapterBase, CostSink
from ai_shorts.config import get_settings


class TypecastTTSResult(BaseModel):
    audio_bytes: bytes
    content_type: str
    voice_id: str
    model: str
    audio_format: str
    text_length: int = Field(ge=1)
    language: str | None = None


class TypecastAdapter(AdapterBase):
    service_name = "typecast"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        voice_id: str | None = None,
        model: str | None = None,
        api_version: str = "v1",
        base_url: str = "https://api.typecast.ai",
        timeout_seconds: float = 60.0,
        estimated_unit_usd: Decimal = Decimal("0.02"),
        client: httpx.AsyncClient | None = None,
        cost_sink: CostSink | None = None,
    ) -> None:
        super().__init__(cost_sink=cost_sink)
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.typecast_api_key
        self.voice_id = voice_id if voice_id is not None else settings.typecast_voice_id
        self.model = model or settings.typecast_model
        self.api_version = api_version
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.estimated_unit_usd = estimated_unit_usd
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)
        self._owns_client = client is None

    async def synthesize(
        self,
        text: str,
        *,
        voice_id: str | None = None,
        language: str | None = "kor",
        prompt: dict[str, object] | None = None,
        volume: int = 100,
        audio_pitch: int = 0,
        audio_tempo: float = 1.0,
        audio_format: str = "wav",
        seed: int | None = None,
        metadata: dict[str, object] | None = None,
    ) -> TypecastTTSResult:
        """Synthesize speech with Typecast's text-to-speech endpoint."""

        if not self.api_key:
            raise RuntimeError("Missing TYPECAST_API_KEY")

        target_voice_id = voice_id or self.voice_id
        if not target_voice_id:
            raise RuntimeError("Missing TYPECAST_VOICE_ID")
        if not text.strip():
            raise RuntimeError("Typecast text must not be empty")
        if len(text) > 2000:
            raise RuntimeError("Typecast text must be 2000 characters or fewer")

        payload = self._build_payload(
            text=text,
            voice_id=target_voice_id,
            language=language,
            prompt=prompt,
            volume=volume,
            audio_pitch=audio_pitch,
            audio_tempo=audio_tempo,
            audio_format=audio_format,
            seed=seed,
        )
        response = await self._client.post(
            self._text_to_speech_url(),
            headers={
                "Content-Type": "application/json",
                "X-API-KEY": self.api_key,
            },
            json=payload,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Typecast request failed: {response.status_code} {response.text}"
            ) from exc

        audio_bytes = response.content
        if not audio_bytes:
            raise RuntimeError("Typecast response did not include audio bytes")

        billable_units = _text_units(len(text))
        result = TypecastTTSResult(
            audio_bytes=audio_bytes,
            content_type=response.headers.get("content-type", f"audio/{audio_format}"),
            voice_id=target_voice_id,
            model=self.model,
            language=language,
            audio_format=audio_format,
            text_length=len(text),
        )
        await self.record_cost(
            operation="text-to-speech",
            usd=self.estimate_cost("text-to-speech", units=billable_units),
            metadata={
                "model": self.model,
                "voice_id": target_voice_id,
                "language": language or "",
                "audio_format": audio_format,
                "text_length": len(text),
                "billable_units": billable_units,
                **(metadata or {}),
            },
        )
        return result

    def estimate_cost(self, operation: str, units: int = 1) -> Decimal:
        if operation not in {"text-to-speech", "synthesize", "tts"}:
            return Decimal("0")
        return self.estimated_unit_usd * max(units, 1)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _text_to_speech_url(self) -> str:
        return f"{self.base_url}/{self.api_version}/text-to-speech"

    def _build_payload(
        self,
        *,
        text: str,
        voice_id: str,
        language: str | None,
        prompt: dict[str, object] | None,
        volume: int,
        audio_pitch: int,
        audio_tempo: float,
        audio_format: str,
        seed: int | None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "voice_id": voice_id,
            "text": text,
            "model": self.model,
            "output": {
                "volume": volume,
                "audio_pitch": audio_pitch,
                "audio_tempo": audio_tempo,
                "audio_format": audio_format,
            },
        }
        if language:
            payload["language"] = language
        if prompt:
            payload["prompt"] = prompt
        if seed is not None:
            payload["seed"] = seed
        return payload


def _text_units(text_length: int) -> int:
    return max(1, (text_length + 999) // 1000)
