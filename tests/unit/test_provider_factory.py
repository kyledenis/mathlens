"""Unit tests for the provider factory functions."""

from __future__ import annotations

import pytest

from mathlens.config.settings import MathLensSettings
from mathlens.providers import build_providers, build_router
from mathlens.providers.api import AnthropicAPIProvider
from mathlens.providers.cli_sub import CLISubprocessProvider
from mathlens.providers.local import OllamaProvider
from mathlens.providers.router import ProviderRouter


def test_builds_local_and_cli_providers() -> None:
    settings = MathLensSettings()
    providers = build_providers(settings)
    assert isinstance(providers["local"], OllamaProvider)
    assert isinstance(providers["cli"], CLISubprocessProvider)


def test_api_provider_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-abc123")
    providers = build_providers(MathLensSettings())
    assert isinstance(providers["api"], AnthropicAPIProvider)

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    providers = build_providers(MathLensSettings())
    assert "api" not in providers


def test_builds_router_with_fallback_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    settings = MathLensSettings()
    providers = build_providers(settings)
    router = build_router(settings, providers)
    assert isinstance(router, ProviderRouter)
    assert router._fallback_chain == settings.provider.fallback_chain
