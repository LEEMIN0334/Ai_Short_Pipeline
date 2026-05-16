from decimal import Decimal
from typing import Any

import httpx
from pydantic import BaseModel

from ai_shorts.adapters.base import AdapterBase, CostSink
from ai_shorts.config import get_settings


class GeminiGenerateResult(BaseModel):
    text: str
    model: str
    raw: dict[str, Any]
    usage_metadata: dict[str, object] | None = None


class GeminiAdapter(AdapterBase):
    service_name = "gemini"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        api_version: str = "v1beta",
        base_url: str = "https://generativelanguage.googleapis.com",
        timeout_seconds: float = 30.0,
        estimated_unit_usd: Decimal = Decimal("0.01"),
        client: httpx.AsyncClient | None = None,
        cost_sink: CostSink | None = None,
    ) -> None:
        super().__init__(cost_sink=cost_sink)
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.gemini_api_key
        self.model = model or settings.gemini_model
        self.api_version = api_version
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.estimated_unit_usd = estimated_unit_usd
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)
        self._owns_client = client is None

    async def generate_text(
        self,
        prompt: str,
        *,
        system_instruction: str | None = None,
        generation_config: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> GeminiGenerateResult:
        """Generate text using Gemini's REST generateContent endpoint."""

        if not self.api_key:
            raise RuntimeError("Missing GEMINI_API_KEY")

        payload = _generate_content_payload(
            prompt,
            system_instruction=system_instruction,
            generation_config=generation_config,
        )
        response = await self._client.post(
            self._generate_content_url(),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
            json=payload,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Gemini request failed: {response.status_code} {response.text}"
            ) from exc

        raw = response.json()
        if not isinstance(raw, dict):
            raise RuntimeError("Gemini response was not a JSON object")

        result = GeminiGenerateResult(
            text=_extract_text(raw),
            model=self.model,
            raw=raw,
            usage_metadata=_usage_metadata(raw),
        )
        await self.record_cost(
            operation="generateContent",
            usd=self.estimate_cost("generateContent"),
            metadata={
                "model": self.model,
                "prompt_length": len(prompt),
                "usage_metadata": result.usage_metadata or {},
                **(metadata or {}),
            },
        )
        return result

    def estimate_cost(self, operation: str, units: int = 1) -> Decimal:
        if operation not in {"generateContent", "generate_text"}:
            return Decimal("0")
        return self.estimated_unit_usd * units

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _generate_content_url(self) -> str:
        model_path = self.model if self.model.startswith("models/") else f"models/{self.model}"
        return f"{self.base_url}/{self.api_version}/{model_path}:generateContent"


def _generate_content_payload(
    prompt: str,
    *,
    system_instruction: str | None,
    generation_config: dict[str, object] | None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ]
    }
    if system_instruction:
        payload["systemInstruction"] = {
            "parts": [{"text": system_instruction}],
        }
    if generation_config:
        payload["generationConfig"] = generation_config
    return payload


def _extract_text(raw: dict[str, Any]) -> str:
    candidates = raw.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise RuntimeError("Gemini response did not include candidates")

    first_candidate = candidates[0]
    if not isinstance(first_candidate, dict):
        raise RuntimeError("Gemini response candidate was not an object")

    content = first_candidate.get("content")
    if not isinstance(content, dict):
        raise RuntimeError("Gemini response candidate did not include content")

    parts = content.get("parts")
    if not isinstance(parts, list):
        raise RuntimeError("Gemini response content did not include parts")

    text_parts = [
        part["text"]
        for part in parts
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    ]
    if not text_parts:
        raise RuntimeError("Gemini response did not include text")
    return "".join(text_parts)


def _usage_metadata(raw: dict[str, Any]) -> dict[str, object] | None:
    usage_metadata = raw.get("usageMetadata")
    if isinstance(usage_metadata, dict):
        return usage_metadata
    return None
