"""Anthropic API provider using httpx."""

from __future__ import annotations

import os
from typing import Optional

import httpx

from mathlens.lifecycle import register_client
from mathlens.providers.base import LLMResponse, ProviderCapabilities, Tier

_API_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"


class AnthropicAPIProvider:
    """LLM provider that calls the Anthropic Messages API directly."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-6",
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._client = httpx.AsyncClient(timeout=600.0)  # 10 min — only catches hangs
        register_client(self._client)

    @classmethod
    def from_env(cls, model: str = "claude-sonnet-4-6") -> Optional[AnthropicAPIProvider]:
        """Create provider from ANTHROPIC_API_KEY env var, or return None if missing."""
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return None
        return cls(api_key=api_key, model=model)

    @property
    def name(self) -> str:
        return "api:anthropic"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            max_context=200_000,
            supports_json_mode=True,
            supports_streaming=True,
            formalization_quality=Tier.HIGH,
            scene_planning_quality=Tier.HIGH,
            summarization_quality=Tier.HIGH,
        )

    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        response_format: str = "text",
    ) -> LLMResponse:
        """Send a completion request to the Anthropic Messages API."""
        if response_format == "json":
            prompt = prompt + "\n\nRespond with valid JSON only."

        body: dict = {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system is not None:
            body["system"] = system

        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

        response = await self._client.post(_API_URL, json=body, headers=headers)
        response.raise_for_status()

        data = response.json()
        content = "".join(
            block["text"] for block in data.get("content", []) if block.get("type") == "text"
        )
        return LLMResponse(
            content=content,
            model=data.get("model", self._model),
            usage=data.get("usage", {}),
        )

    async def health_check(self) -> bool:
        """Return True if the API responds successfully, False on any exception."""
        try:
            await self.complete("Say 'ok'", max_tokens=8)
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """Close the underlying httpx client."""
        await self._client.aclose()
