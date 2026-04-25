"""Unit tests for the Anthropic API provider."""

from __future__ import annotations

import pytest
import respx
import httpx

from mathlens.providers.api import AnthropicAPIProvider


_FAKE_KEY = "test-api-key-abc123"
_API_URL = "https://api.anthropic.com/v1/messages"

_MOCK_RESPONSE = {
    "id": "msg_01XFDUDYJgAACzvnptvVoYEL",
    "type": "message",
    "role": "assistant",
    "model": "claude-sonnet-4-6",
    "content": [{"type": "text", "text": "Hello, world!"}],
    "stop_reason": "end_turn",
    "usage": {"input_tokens": 10, "output_tokens": 5},
}


@pytest.fixture
def provider():
    return AnthropicAPIProvider(api_key=_FAKE_KEY)


class TestCompleteSuccess:
    @respx.mock
    async def test_complete_success(self, provider):
        respx.post(_API_URL).mock(return_value=httpx.Response(200, json=_MOCK_RESPONSE))

        result = await provider.complete("Hello")

        assert result.content == "Hello, world!"
        assert result.model == "claude-sonnet-4-6"
        assert result.usage == {"input_tokens": 10, "output_tokens": 5}

    @respx.mock
    async def test_complete_with_system(self, provider):
        route = respx.post(_API_URL).mock(return_value=httpx.Response(200, json=_MOCK_RESPONSE))

        await provider.complete("Hello", system="You are a tutor.")

        request_body = route.calls.last.request
        import json
        body = json.loads(request_body.content)
        assert body["system"] == "You are a tutor."

    @respx.mock
    async def test_complete_json_format_appends_instruction(self, provider):
        route = respx.post(_API_URL).mock(return_value=httpx.Response(200, json=_MOCK_RESPONSE))

        await provider.complete("Give me data", response_format="json")

        import json
        body = json.loads(route.calls.last.request.content)
        assert body["messages"][0]["content"].endswith("\n\nRespond with valid JSON only.")


class TestCompleteErrors:
    @respx.mock
    async def test_complete_api_error_raises(self, provider):
        respx.post(_API_URL).mock(return_value=httpx.Response(429, json={"error": "rate limited"}))

        with pytest.raises(httpx.HTTPStatusError):
            await provider.complete("Hello")


class TestHealthCheck:
    @respx.mock
    async def test_health_check(self, provider):
        respx.post(_API_URL).mock(return_value=httpx.Response(200, json=_MOCK_RESPONSE))
        assert await provider.health_check() is True

    @respx.mock
    async def test_health_check_failure(self, provider):
        respx.post(_API_URL).mock(return_value=httpx.Response(401, json={"error": "unauthorized"}))
        assert await provider.health_check() is False


class TestFromEnv:
    def test_from_env_with_and_without_key(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key-xyz")
        assert AnthropicAPIProvider.from_env() is not None

        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert AnthropicAPIProvider.from_env() is None
