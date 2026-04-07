"""Unit tests for OllamaProvider."""

from __future__ import annotations

import pytest
import respx
import httpx

from mathlens.providers.local import OllamaProvider, _estimate_tiers
from mathlens.providers.base import Tier


class TestOllamaProviderName:
    def test_name(self):
        provider = OllamaProvider()
        assert provider.name == "local:ollama"


class TestEstimateTiers:
    def test_capabilities_large_model(self):
        provider = OllamaProvider(model="qwen3:32b")
        caps = provider.capabilities
        assert caps.formalization_quality == Tier.LOW
        assert caps.scene_planning_quality == Tier.MEDIUM
        assert caps.summarization_quality == Tier.HIGH

    def test_capabilities_small_model(self):
        provider = OllamaProvider(model="qwen3:8b")
        caps = provider.capabilities
        assert caps.scene_planning_quality == Tier.LOW

    def test_large_model_threshold_30b(self):
        formalization, scene, summary = _estimate_tiers("llama3:30b")
        assert formalization == Tier.LOW
        assert scene == Tier.MEDIUM
        assert summary == Tier.HIGH

    def test_medium_model_threshold_14b(self):
        formalization, scene, summary = _estimate_tiers("llama3:14b")
        assert formalization == Tier.LOW
        assert scene == Tier.MEDIUM
        assert summary == Tier.MEDIUM

    def test_small_model_below_14b(self):
        formalization, scene, summary = _estimate_tiers("llama3:7b")
        assert formalization == Tier.LOW
        assert scene == Tier.LOW
        assert summary == Tier.MEDIUM

    def test_no_param_count_defaults_to_7b(self):
        formalization, scene, summary = _estimate_tiers("unknown-model")
        assert formalization == Tier.LOW
        assert scene == Tier.LOW
        assert summary == Tier.MEDIUM

    def test_uppercase_b_in_model_name(self):
        formalization, scene, summary = _estimate_tiers("model:32B")
        assert summary == Tier.HIGH

    def test_formalization_always_low(self):
        for model in ["qwen3:8b", "qwen3:14b", "qwen3:32b", "qwen3:70b"]:
            formalization, _, _ = _estimate_tiers(model)
            assert formalization == Tier.LOW, f"Expected LOW for {model}"


class TestOllamaProviderCapabilities:
    def test_capabilities_defaults(self):
        provider = OllamaProvider()
        caps = provider.capabilities
        assert caps.max_context == 32_000
        assert caps.supports_json_mode is True
        assert caps.supports_streaming is True

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
    async def test_complete_with_system(self):
        mock_response = {
            "model": "qwen3:32b",
            "response": "Sure thing.",
            "done": True,
        }
        route = respx.post("http://localhost:11434/api/generate").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        provider = OllamaProvider(model="qwen3:32b")
        await provider.complete("Hello", system="You are a helpful assistant.")

        request_body = route.calls[0].request
        import json
        body = json.loads(request_body.content)
        assert body["system"] == "You are a helpful assistant."

    @pytest.mark.asyncio
    @respx.mock
    async def test_complete_json_format(self):
        mock_response = {
            "model": "qwen3:32b",
            "response": '{"result": 42}',
            "done": True,
        }
        route = respx.post("http://localhost:11434/api/generate").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        provider = OllamaProvider(model="qwen3:32b")
        result = await provider.complete("Compute", response_format="json")

        import json
        body = json.loads(route.calls[0].request.content)
        assert body["format"] == "json"
        assert result.content == '{"result": 42}'

    @pytest.mark.asyncio
    @respx.mock
    async def test_complete_passes_options(self):
        mock_response = {
            "model": "qwen3:32b",
            "response": "ok",
            "done": True,
        }
        route = respx.post("http://localhost:11434/api/generate").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        provider = OllamaProvider(model="qwen3:32b")
        await provider.complete("prompt", temperature=0.7, max_tokens=512)

        import json
        body = json.loads(route.calls[0].request.content)
        assert body["options"]["temperature"] == 0.7
        assert body["options"]["num_predict"] == 512
        assert body["stream"] is False


class TestOllamaProviderHealthCheck:
    @pytest.mark.asyncio
    @respx.mock
    async def test_health_check_success(self):
        respx.get("http://localhost:11434/api/tags").mock(
            return_value=httpx.Response(200, json={"models": []})
        )

        provider = OllamaProvider()
        result = await provider.health_check()
        assert result is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_health_check_connection_refused(self):
        respx.get("http://localhost:11434/api/tags").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        provider = OllamaProvider()
        result = await provider.health_check()
        assert result is False
