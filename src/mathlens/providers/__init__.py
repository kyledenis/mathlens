"""LLM provider abstraction for MathLens."""

from __future__ import annotations

import asyncio
import os
import shutil

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


async def auto_detect_provider(settings: MathLensSettings) -> tuple[str, LLMProvider]:
    """Detect the best available provider. Returns (name, provider).

    Priority: user's configured default > api (if key set) > cli (if installed) > local (if running)
    """
    providers = build_providers(settings)

    # If user explicitly configured a default, try it first
    default = settings.provider.default
    if default in providers:
        provider = providers[default]
        if await provider.health_check():
            return default, provider

    # Auto-detect: API > CLI > Local
    for name in ["api", "cli", "local"]:
        if name in providers:
            try:
                if await providers[name].health_check():
                    return name, providers[name]
            except Exception:
                continue

    raise RuntimeError("No LLM provider available. Run `mathlens doctor` to check dependencies.")


async def detect_local_models(endpoint: str = "http://localhost:1234/v1") -> list[dict]:
    """Query an OpenAI-compatible endpoint for available models."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{endpoint}/models")
            if resp.status_code == 200:
                return resp.json().get("data", [])
    except Exception:
        pass
    return []


__all__ = [
    "LLMProvider",
    "ProviderRouter",
    "auto_detect_provider",
    "build_providers",
    "build_router",
    "detect_local_models",
]
