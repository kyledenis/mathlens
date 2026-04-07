"""Unit tests for the provider factory functions."""

from __future__ import annotations

import pytest

from mathlens.config.settings import MathLensSettings
from mathlens.providers import build_providers, build_router
from mathlens.providers.api import AnthropicAPIProvider
from mathlens.providers.cli_sub import CLISubprocessProvider
from mathlens.providers.local import OllamaProvider
from mathlens.providers.router import ProviderRouter


def test_builds_local_provider() -> None:
    settings = MathLensSettings()
    providers = build_providers(settings)
    assert "local" in providers
    assert isinstance(providers["local"], OllamaProvider)


def test_builds_cli_provider() -> None:
    settings = MathLensSettings()
    providers = build_providers(settings)
    assert "cli" in providers
    assert isinstance(providers["cli"], CLISubprocessProvider)


def test_builds_api_provider_with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-abc123")
    settings = MathLensSettings()
    providers = build_providers(settings)
    assert "api" in providers
    assert isinstance(providers["api"], AnthropicAPIProvider)


def test_skips_api_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    settings = MathLensSettings()
    providers = build_providers(settings)
    assert "api" not in providers


def test_builds_router_with_fallback_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    settings = MathLensSettings()
    providers = build_providers(settings)
    router = build_router(settings, providers)
    assert isinstance(router, ProviderRouter)
    # Verify the router was wired with the expected fallback chain from settings
    assert router._fallback_chain == settings.provider.fallback_chain
