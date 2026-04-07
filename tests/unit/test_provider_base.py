"""Unit tests for LLM provider base types."""

import pytest

from mathlens.providers.base import (
    LLMResponse,
    ProviderCapabilities,
    Tier,
    TaskType,
    TASK_MINIMUM_TIERS,
)


class TestTierEnum:
    def test_values(self):
        assert Tier.HIGH == "high"
        assert Tier.MEDIUM == "medium"
        assert Tier.LOW == "low"

    def test_is_str(self):
        assert isinstance(Tier.HIGH, str)

    def test_high_greater_than_medium(self):
        assert Tier.HIGH > Tier.MEDIUM

    def test_high_greater_than_low(self):
        assert Tier.HIGH > Tier.LOW

    def test_medium_greater_than_low(self):
        assert Tier.MEDIUM > Tier.LOW

    def test_high_ge_high(self):
        assert Tier.HIGH >= Tier.HIGH

    def test_low_le_high(self):
        assert Tier.LOW <= Tier.HIGH

    def test_low_not_greater_than_medium(self):
        assert not (Tier.LOW > Tier.MEDIUM)

    def test_medium_not_greater_than_high(self):
        assert not (Tier.MEDIUM > Tier.HIGH)


class TestTaskTypeEnum:
    def test_values(self):
        assert TaskType.FORMALIZATION == "formalization"
        assert TaskType.SCENE_PLANNING == "scene_planning"
        assert TaskType.SUMMARIZATION == "summarization"
        assert TaskType.INTENT_PARSING == "intent_parsing"

    def test_is_str(self):
        assert isinstance(TaskType.FORMALIZATION, str)


class TestTaskMinimumTiers:
    def test_formalization_requires_high(self):
        assert TASK_MINIMUM_TIERS[TaskType.FORMALIZATION] == Tier.HIGH

    def test_scene_planning_requires_medium(self):
        assert TASK_MINIMUM_TIERS[TaskType.SCENE_PLANNING] == Tier.MEDIUM

    def test_summarization_requires_low(self):
        assert TASK_MINIMUM_TIERS[TaskType.SUMMARIZATION] == Tier.LOW

    def test_intent_parsing_requires_medium(self):
        assert TASK_MINIMUM_TIERS[TaskType.INTENT_PARSING] == Tier.MEDIUM

    def test_all_task_types_covered(self):
        for task in TaskType:
            assert task in TASK_MINIMUM_TIERS


class TestLLMResponse:
    def test_creation(self):
        resp = LLMResponse(content="hello", model="claude-3-5-sonnet")
        assert resp.content == "hello"
        assert resp.model == "claude-3-5-sonnet"

    def test_usage_defaults_to_empty_dict(self):
        resp = LLMResponse(content="hello", model="claude-3-5-sonnet")
        assert resp.usage == {}

    def test_usage_can_be_set(self):
        resp = LLMResponse(
            content="hello",
            model="claude-3-5-sonnet",
            usage={"input_tokens": 10, "output_tokens": 20},
        )
        assert resp.usage["input_tokens"] == 10


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

    def test_tier_for_formalization(self):
        caps = self._make_caps(formalization_quality=Tier.HIGH)
        assert caps.tier_for_task(TaskType.FORMALIZATION) == Tier.HIGH

    def test_tier_for_scene_planning(self):
        caps = self._make_caps(scene_planning_quality=Tier.MEDIUM)
        assert caps.tier_for_task(TaskType.SCENE_PLANNING) == Tier.MEDIUM

    def test_tier_for_summarization(self):
        caps = self._make_caps(summarization_quality=Tier.LOW)
        assert caps.tier_for_task(TaskType.SUMMARIZATION) == Tier.LOW

    def test_tier_for_intent_parsing_maps_to_scene_planning_quality(self):
        caps = self._make_caps(scene_planning_quality=Tier.MEDIUM)
        assert caps.tier_for_task(TaskType.INTENT_PARSING) == Tier.MEDIUM

    def test_meets_tier_high_meets_high(self):
        caps = self._make_caps(formalization_quality=Tier.HIGH)
        assert caps.meets_tier(TaskType.FORMALIZATION, Tier.HIGH) is True

    def test_meets_tier_high_meets_medium(self):
        caps = self._make_caps(scene_planning_quality=Tier.HIGH)
        assert caps.meets_tier(TaskType.SCENE_PLANNING, Tier.MEDIUM) is True

    def test_meets_tier_high_meets_low(self):
        caps = self._make_caps(summarization_quality=Tier.HIGH)
        assert caps.meets_tier(TaskType.SUMMARIZATION, Tier.LOW) is True

    def test_meets_tier_low_does_not_meet_high(self):
        caps = self._make_caps(formalization_quality=Tier.LOW)
        assert caps.meets_tier(TaskType.FORMALIZATION, Tier.HIGH) is False

    def test_meets_tier_low_does_not_meet_medium(self):
        caps = self._make_caps(scene_planning_quality=Tier.LOW)
        assert caps.meets_tier(TaskType.SCENE_PLANNING, Tier.MEDIUM) is False

    def test_meets_tier_medium_meets_medium(self):
        caps = self._make_caps(scene_planning_quality=Tier.MEDIUM)
        assert caps.meets_tier(TaskType.SCENE_PLANNING, Tier.MEDIUM) is True

    def test_meets_tier_medium_does_not_meet_high(self):
        caps = self._make_caps(formalization_quality=Tier.MEDIUM)
        assert caps.meets_tier(TaskType.FORMALIZATION, Tier.HIGH) is False
