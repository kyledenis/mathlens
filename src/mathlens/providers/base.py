"""Provider protocol and shared types for LLM integrations."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Tier enum with ordering
# ---------------------------------------------------------------------------

_TIER_ORDER = {"high": 2, "medium": 1, "low": 0}


class Tier(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    def _rank(self) -> int:
        return _TIER_ORDER[self.value]

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Tier):
            return NotImplemented
        return self._rank() > other._rank()

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Tier):
            return NotImplemented
        return self._rank() >= other._rank()

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Tier):
            return NotImplemented
        return self._rank() < other._rank()

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Tier):
            return NotImplemented
        return self._rank() <= other._rank()


# ---------------------------------------------------------------------------
# TaskType enum
# ---------------------------------------------------------------------------


class TaskType(str, Enum):
    FORMALIZATION = "formalization"
    SCENE_PLANNING = "scene_planning"
    SUMMARIZATION = "summarization"
    INTENT_PARSING = "intent_parsing"


# ---------------------------------------------------------------------------
# Minimum tier requirements per task
# ---------------------------------------------------------------------------

TASK_MINIMUM_TIERS: dict[TaskType, Tier] = {
    TaskType.FORMALIZATION: Tier.HIGH,
    TaskType.SCENE_PLANNING: Tier.MEDIUM,
    TaskType.SUMMARIZATION: Tier.LOW,
    TaskType.INTENT_PARSING: Tier.MEDIUM,
}


# ---------------------------------------------------------------------------
# Pydantic response/capability models
# ---------------------------------------------------------------------------


class LLMResponse(BaseModel):
    content: str
    model: str
    usage: dict[str, Any] = Field(default_factory=dict)


class ProviderCapabilities(BaseModel):
    max_context: int
    supports_json_mode: bool
    supports_streaming: bool
    formalization_quality: Tier
    scene_planning_quality: Tier
    summarization_quality: Tier

    def tier_for_task(self, task: TaskType) -> Tier:
        """Return the capability tier for the given task type."""
        if task == TaskType.FORMALIZATION:
            return self.formalization_quality
        if task in (TaskType.SCENE_PLANNING, TaskType.INTENT_PARSING):
            return self.scene_planning_quality
        if task == TaskType.SUMMARIZATION:
            return self.summarization_quality
        raise ValueError(f"Unknown task type: {task}")

    def meets_tier(self, task: TaskType, required: Tier) -> bool:
        """Return True if this provider's capability meets or exceeds required tier."""
        return self.tier_for_task(task) >= required


# ---------------------------------------------------------------------------
# LLMProvider Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class LLMProvider(Protocol):
    @property
    def name(self) -> str:
        ...

    @property
    def capabilities(self) -> ProviderCapabilities:
        ...

    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        response_format: str = "text",
    ) -> LLMResponse:
        ...

    async def health_check(self) -> bool:
        ...


def is_small_model(model_name: str) -> bool:
    """Return True if the model name suggests a small (<14B) parameter count."""
    import re

    match = re.search(r'(\d+)[bB]', model_name)
    if match:
        return int(match.group(1)) < 14
    return False
