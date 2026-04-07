"""Unit tests for ProviderRouter."""

import pytest
from unittest.mock import AsyncMock, MagicMock, PropertyMock

from mathlens.providers.base import (
    Tier,
    TaskType,
    ProviderCapabilities,
)
from mathlens.providers.router import ProviderRouter


def _make_provider(
    name: str,
    formalization: Tier = Tier.HIGH,
    scene: Tier = Tier.HIGH,
    summarization: Tier = Tier.HIGH,
    healthy: bool = True,
):
    """Create an AsyncMock provider with configured capabilities and health."""
    provider = AsyncMock()

    # name property
    name_prop = PropertyMock(return_value=name)
    type(provider).name = name_prop

    # capabilities property
    caps = ProviderCapabilities(
        max_context=200000,
        supports_json_mode=True,
        supports_streaming=True,
        formalization_quality=formalization,
        scene_planning_quality=scene,
        summarization_quality=summarization,
    )
    caps_prop = PropertyMock(return_value=caps)
    type(provider).capabilities = caps_prop

    # health_check
    provider.health_check = AsyncMock(return_value=healthy)

    return provider


class TestProviderRouterSelectsFirstCapable:
    async def test_selects_first_capable_provider(self):
        api = _make_provider("api", formalization=Tier.HIGH)
        local = _make_provider("local", formalization=Tier.HIGH)
        router = ProviderRouter(
            providers={"api": api, "local": local},
            fallback_chain=["api", "local"],
        )
        result = await router.for_task(TaskType.FORMALIZATION)
        assert result is api

    async def test_no_capable_provider_raises(self):
        local = _make_provider("local", formalization=Tier.LOW)
        router = ProviderRouter(
            providers={"local": local},
            fallback_chain=["local"],
        )
        with pytest.raises(RuntimeError, match="No provider available"):
            await router.for_task(TaskType.FORMALIZATION)

    async def test_skips_unhealthy_provider(self):
        sick_api = _make_provider("api", summarization=Tier.HIGH, healthy=False)
        healthy_local = _make_provider("local", summarization=Tier.HIGH, healthy=True)
        router = ProviderRouter(
            providers={"api": sick_api, "local": healthy_local},
            fallback_chain=["api", "local"],
        )
        result = await router.for_task(TaskType.SUMMARIZATION)
        assert result is healthy_local

    async def test_prefer_local_for_summarization(self):
        api = _make_provider("api", summarization=Tier.HIGH, healthy=True)
        local = _make_provider("local", summarization=Tier.HIGH, healthy=True)
        router = ProviderRouter(
            providers={"api": api, "local": local},
            fallback_chain=["local", "api"],
        )
        result = await router.for_task(TaskType.SUMMARIZATION)
        assert result is local


class TestProviderRouterHealthCache:
    async def test_health_cached_after_first_check(self):
        provider = _make_provider("api", healthy=True)
        router = ProviderRouter(
            providers={"api": provider},
            fallback_chain=["api"],
        )
        await router.for_task(TaskType.SUMMARIZATION)
        await router.for_task(TaskType.SUMMARIZATION)
        # health_check called once due to caching
        assert provider.health_check.call_count == 1

    async def test_invalidate_health_clears_cache(self):
        provider = _make_provider("api", healthy=True)
        router = ProviderRouter(
            providers={"api": provider},
            fallback_chain=["api"],
        )
        await router.for_task(TaskType.SUMMARIZATION)
        router.invalidate_health("api")
        await router.for_task(TaskType.SUMMARIZATION)
        assert provider.health_check.call_count == 2

    async def test_invalidate_all_clears_all(self):
        api = _make_provider("api", healthy=True)
        local = _make_provider("local", healthy=True)
        router = ProviderRouter(
            providers={"api": api, "local": local},
            fallback_chain=["api", "local"],
        )
        await router.for_task(TaskType.SUMMARIZATION)
        router.invalidate_health()
        await router.for_task(TaskType.SUMMARIZATION)
        # After full invalidation, api is re-checked (and wins first again)
        assert api.health_check.call_count == 2
