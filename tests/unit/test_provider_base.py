"""Unit tests for LLM provider base types."""

import pytest

from mathlens.providers.base import (
    ProviderCapabilities,
    Tier,
    TaskType,
    TASK_MINIMUM_TIERS,
)


class TestTierOrdering:
    """Tier has custom comparison operators — these test real logic."""

    def test_ordering(self):
        assert Tier.HIGH > Tier.MEDIUM > Tier.LOW
        assert Tier.HIGH >= Tier.HIGH
        assert Tier.LOW <= Tier.HIGH
        assert not (Tier.LOW > Tier.MEDIUM)

    def test_all_task_types_have_minimum_tiers(self):
        for task in TaskType:
            assert task in TASK_MINIMUM_TIERS


class TestProviderCapabilities:
    def _make_caps(
        self,
        formalization_quality=Tier.HIGH,
        scene_planning_quality=Tier.MEDIUM,
        summarization_quality=Tier.LOW,
    ):
        return ProviderCapabilities(
            max_context=200000,
            supports_json_mode=True,
            supports_streaming=True,
            formalization_quality=formalization_quality,
            scene_planning_quality=scene_planning_quality,
            summarization_quality=summarization_quality,
        )

    def test_tier_for_task_mapping(self):
        caps = self._make_caps()
        assert caps.tier_for_task(TaskType.FORMALIZATION) == Tier.HIGH
        assert caps.tier_for_task(TaskType.SCENE_PLANNING) == Tier.MEDIUM
        assert caps.tier_for_task(TaskType.SUMMARIZATION) == Tier.LOW
        # intent_parsing maps to scene_planning_quality
        assert caps.tier_for_task(TaskType.INTENT_PARSING) == Tier.MEDIUM

    def test_meets_tier_pass(self):
        caps = self._make_caps(formalization_quality=Tier.HIGH)
        assert caps.meets_tier(TaskType.FORMALIZATION, Tier.HIGH) is True
        assert caps.meets_tier(TaskType.FORMALIZATION, Tier.MEDIUM) is True

    def test_meets_tier_fail(self):
        caps = self._make_caps(formalization_quality=Tier.LOW)
        assert caps.meets_tier(TaskType.FORMALIZATION, Tier.HIGH) is False
