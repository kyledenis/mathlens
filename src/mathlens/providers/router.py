"""Task-aware LLM provider router."""

from __future__ import annotations

from typing import Optional

from mathlens.providers.base import LLMProvider, TaskType, TASK_MINIMUM_TIERS


class ProviderRouter:
    """Routes tasks to the best available LLM provider.

    Iterates fallback_chain in order, selecting the first provider that
    meets the minimum tier requirement for the task and passes a health check.
    Health check results are cached to avoid redundant calls.
    """

    def __init__(
        self,
        providers: dict[str, LLMProvider],
        fallback_chain: list[str],
    ) -> None:
        self._providers = providers
        self._fallback_chain = fallback_chain
        self._health_cache: dict[str, bool] = {}

    async def for_task(self, task: TaskType) -> LLMProvider:
        """Return the first capable, healthy provider for the given task.

        Raises RuntimeError if no suitable provider is found.
        """
        required_tier = TASK_MINIMUM_TIERS[task]

        for name in self._fallback_chain:
            provider = self._providers.get(name)
            if provider is None:
                continue

            if not provider.capabilities.meets_tier(task, required_tier):
                continue

            if await self._is_healthy(name, provider):
                return provider

        raise RuntimeError(
            f"No provider available for task '{task.value}' "
            f"requiring tier '{required_tier.value}'. "
            f"Checked chain: {self._fallback_chain}"
        )

    async def _is_healthy(self, name: str, provider: LLMProvider) -> bool:
        """Return cached health status, calling health_check if not cached."""
        if name not in self._health_cache:
            self._health_cache[name] = await provider.health_check()
        return self._health_cache[name]

    def invalidate_health(self, name: Optional[str] = None) -> None:
        """Clear health cache for a specific provider, or all providers if name is None."""
        if name is None:
            self._health_cache.clear()
        else:
            self._health_cache.pop(name, None)
