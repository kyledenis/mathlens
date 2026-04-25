"""Unit tests for OllamaProvider."""

from __future__ import annotations

import pytest
import respx
import httpx

from mathlens.providers.local import OllamaProvider, _estimate_tiers
from mathlens.providers.base import Tier


class TestEstimateTiers:
    def test_tier_estimation_by_model_size(self):
        for model, expected_scene, expected_summary in [
            ("llama3:30b", Tier.MEDIUM, Tier.HIGH),
            ("llama3:7b", Tier.LOW, Tier.MEDIUM),
            ("unknown-model", Tier.LOW, Tier.MEDIUM),
            ("model:32B", Tier.MEDIUM, Tier.HIGH),
        ]:
            formalization, scene, summary = _estimate_tiers(model)
            assert formalization == Tier.LOW, f"Formalization not LOW for {model}"
            assert scene == expected_scene, f"Scene wrong for {model}"
            assert summary == expected_summary, f"Summary wrong for {model}"

    def test_endpoint_trailing_slash_stripped(self):
        provider = OllamaProvider(endpoint="http://localhost:11434/")
        assert provider._endpoint == "http://localhost:11434"


class TestOllamaProviderComplete:
    @pytest.mark.asyncio
    @respx.mock
    async def test_complete_success(self):
        mock_response = {
            "model": "qwen3:32b",
            "response": "The answer is 42.",
            "done": True,
        }
        respx.post("http://localhost:11434/api/generate").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        provider = OllamaProvider(model="qwen3:32b")
        result = await provider.complete("What is 6 times 7?")

        assert result.content == "The answer is 42."
        assert result.model == "qwen3:32b"

    @pytest.mark.asyncio
    @respx.mock
    async def test_complete_passes_options_and_format(self):
        mock_response = {
            "model": "qwen3:32b",
            "response": '{"result": 42}',
            "done": True,
        }
        route = respx.post("http://localhost:11434/api/generate").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        provider = OllamaProvider(model="qwen3:32b")
        await provider.complete("prompt", response_format="json", temperature=0.7, max_tokens=512)

        import json
        body = json.loads(route.calls[0].request.content)
        assert body["format"] == "json"
        assert body["options"]["temperature"] == 0.7
        assert body["options"]["num_predict"] == 512
        assert body["stream"] is False


class TestOllamaProviderHealthCheck:
    @pytest.mark.asyncio
    @respx.mock
    async def test_health_check_success_and_failure(self):
        provider = OllamaProvider()

        respx.get("http://localhost:11434/api/tags").mock(
            return_value=httpx.Response(200, json={"models": []})
        )
        assert await provider.health_check() is True

        respx.get("http://localhost:11434/api/tags").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        assert await provider.health_check() is False
