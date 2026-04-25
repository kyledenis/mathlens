"""LLM provider abstraction for MathLens."""

from __future__ import annotations

from mathlens.config.settings import MathLensSettings
from mathlens.providers.api import AnthropicAPIProvider
from mathlens.providers.base import LLMProvider
from mathlens.providers.cli_sub import CLISubprocessProvider
from mathlens.providers.local import OllamaProvider, OpenAICompatibleProvider
from mathlens.providers.router import ProviderRouter


def build_providers(settings: MathLensSettings) -> dict[str, LLMProvider]:
    providers: dict[str, LLMProvider] = {}
    backend = settings.provider.local.backend
    if backend in ("openai", "lmstudio"):
        providers["local"] = OpenAICompatibleProvider(
            model=settings.provider.local.model,
            endpoint=settings.provider.local.endpoint,
            label=backend,
        )
    else:
        providers["local"] = OllamaProvider(
            model=settings.provider.local.model,
            endpoint=settings.provider.local.endpoint,
        )
    providers["cli"] = CLISubprocessProvider(
        backend=settings.provider.cli.backend,
        timeout=settings.provider.cli.timeout,
        model=settings.provider.cli.model,
        max_budget_usd=settings.provider.cli.max_budget_usd,
    )
    api = AnthropicAPIProvider.from_env(model=settings.provider.api.model)
    if api is not None:
        providers["api"] = api
    return providers


def build_router(settings: MathLensSettings, providers: dict[str, LLMProvider]) -> ProviderRouter:
    return ProviderRouter(providers=providers, fallback_chain=settings.provider.fallback_chain)


__all__ = ["LLMProvider", "ProviderRouter", "build_providers", "build_router"]
