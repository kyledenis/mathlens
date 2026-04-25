"""Local model providers — Ollama native API and OpenAI-compatible API."""

from __future__ import annotations

import re
from typing import Optional

import httpx

from mathlens.lifecycle import register_client
from mathlens.providers.base import LLMResponse, ProviderCapabilities, Tier


def _estimate_tiers(model: str) -> tuple[Tier, Tier, Tier]:
    """Estimate quality tiers based on model parameter count.

    Returns (formalization_tier, scene_planning_tier, summarization_tier).
    Formalization is always LOW for local models.
    """
    match = re.search(r"(\d+)[bB]", model)
    param_count = int(match.group(1)) if match else 7

    if param_count >= 30:
        return (Tier.LOW, Tier.MEDIUM, Tier.HIGH)
    elif param_count >= 14:
        return (Tier.LOW, Tier.MEDIUM, Tier.MEDIUM)
    else:
        return (Tier.LOW, Tier.LOW, Tier.MEDIUM)


# ---------------------------------------------------------------------------
# OpenAI-compatible provider (LM Studio, Ollama /v1, vLLM, etc.)
# ---------------------------------------------------------------------------


class OpenAICompatibleProvider:
    """LLM provider for any OpenAI-compatible API endpoint.

    Works with LM Studio (localhost:1234), Ollama's OpenAI endpoint
    (localhost:11434/v1), vLLM, text-generation-inference, and others.
    """

    def __init__(
        self,
        model: str = "qwen3-32b",
        endpoint: str = "http://localhost:1234/v1",
        label: str = "local",
    ) -> None:
        self._model = model
        self._endpoint = endpoint.rstrip("/")
        self._label = label
        self._client = httpx.AsyncClient(timeout=1800)
        register_client(self._client)
        tiers = _estimate_tiers(model)
        self._formalization_tier = tiers[0]
        self._scene_tier = tiers[1]
        self._summary_tier = tiers[2]

    @property
    def name(self) -> str:
        return f"local:{self._label}"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            max_context=32_000,
            supports_json_mode=True,
            supports_streaming=True,
            formalization_quality=self._formalization_tier,
            scene_planning_quality=self._scene_tier,
            summarization_quality=self._summary_tier,
        )

    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        response_format: str = "text",
    ) -> LLMResponse:
        """Send a chat completion request via the OpenAI-compatible API."""
        messages: list[dict[str, str]] = []
        if system is not None:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body: dict = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format == "json":
            body["response_format"] = {"type": "json_object"}

        response = await self._client.post(
            f"{self._endpoint}/chat/completions",
            json=body,
        )
        response.raise_for_status()

        data = response.json()
        choice = data.get("choices", [{}])[0]
        content = choice.get("message", {}).get("content", "")
        return LLMResponse(
            content=content,
            model=data.get("model", self._model),
            usage=data.get("usage", {}),
        )

    async def health_check(self) -> bool:
        """Return True if the endpoint is reachable."""
        try:
            response = await self._client.get(f"{self._endpoint}/models")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        await self._client.aclose()


# ---------------------------------------------------------------------------
# Ollama native provider
# ---------------------------------------------------------------------------


class OllamaProvider:
    """LLM provider that calls a local Ollama instance."""

    def __init__(
        self,
        model: str = "qwen3:32b",
        endpoint: str = "http://localhost:11434",
    ) -> None:
        self._model = model
        self._endpoint = endpoint.rstrip("/")
        # Local models can be very slow — 30 min catches hangs without interfering
        self._client = httpx.AsyncClient(timeout=1800)
        register_client(self._client)
        tiers = _estimate_tiers(model)
        self._formalization_tier = tiers[0]
        self._scene_tier = tiers[1]
        self._summary_tier = tiers[2]

    @property
    def name(self) -> str:
        return "local:ollama"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            max_context=32_000,
            supports_json_mode=True,
            supports_streaming=True,
            formalization_quality=self._formalization_tier,
            scene_planning_quality=self._scene_tier,
            summarization_quality=self._summary_tier,
        )

    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        response_format: str = "text",
    ) -> LLMResponse:
        """Send a completion request to the Ollama generate API."""
        body: dict = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system is not None:
            body["system"] = system
        if response_format == "json":
            body["format"] = "json"

        response = await self._client.post(
            f"{self._endpoint}/api/generate",
            json=body,
        )
        response.raise_for_status()

        data = response.json()
        return LLMResponse(
            content=data.get("response", ""),
            model=data.get("model", self._model),
            usage=data.get("usage", {}),
        )

    async def health_check(self) -> bool:
        """Return True if Ollama is reachable, False on any exception."""
        try:
            response = await self._client.get(f"{self._endpoint}/api/tags")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        """Close the underlying httpx client."""
        await self._client.aclose()
