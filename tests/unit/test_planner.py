"""Unit tests for the Planner pipeline stage."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from mathlens.models import Difficulty, ExplorationPlan, OutputFormat
from mathlens.pipeline.planner import Planner
from mathlens.providers.base import LLMResponse, ProviderCapabilities, Tier


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "planner_response.json"


@pytest.fixture()
def fixture_content() -> str:
    return FIXTURE_PATH.read_text()


@pytest.fixture()
def fixture_data(fixture_content: str) -> dict:
    return json.loads(fixture_content)


@pytest.fixture()
def mock_provider(fixture_content: str) -> MagicMock:
    provider = MagicMock()
    provider.name = "mock"
    provider.capabilities = ProviderCapabilities(
        max_context=128000,
        supports_json_mode=True,
        supports_streaming=False,
        formalization_quality=Tier.HIGH,
        scene_planning_quality=Tier.MEDIUM,
        summarization_quality=Tier.LOW,
    )
    provider.complete = AsyncMock(
        return_value=LLMResponse(content=fixture_content, model="mock-model")
    )
    return provider


@pytest.fixture()
def planner(mock_provider: MagicMock) -> Planner:
    return Planner(mock_provider)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPlanFromQuery:
    @pytest.mark.asyncio
    async def test_plan_from_query(self, planner: Planner) -> None:
        result = await planner.plan("Prove the harmonic series diverges")
        assert isinstance(result, ExplorationPlan)
        assert result.topic == "harmonic-series-divergence"
        assert result.intent.value == "prove"
        assert len(result.visualization_scenes) == 1
        assert result.visualization_scenes[0].title == "Partial sums growth"

    @pytest.mark.asyncio
    async def test_plan_generates_slug(self, planner: Planner) -> None:
        result = await planner.plan("Prove the harmonic series diverges")
        assert "harmonic-series-divergence" in result.slug

    @pytest.mark.asyncio
    async def test_plan_output_format(self, planner: Planner) -> None:
        result = await planner.plan("Prove the harmonic series diverges")
        assert result.output_format == OutputFormat.video

    @pytest.mark.asyncio
    async def test_plan_difficulty(self, planner: Planner) -> None:
        result = await planner.plan("Prove the harmonic series diverges")
        assert result.difficulty == Difficulty.intermediate

    @pytest.mark.asyncio
    async def test_plan_with_format_override(self, planner: Planner) -> None:
        result = await planner.plan(
            "Prove the harmonic series diverges",
            output_format=OutputFormat.diagram,
        )
        assert result.output_format == OutputFormat.diagram

    @pytest.mark.asyncio
    async def test_plan_sends_structured_prompt(
        self, planner: Planner, mock_provider: MagicMock
    ) -> None:
        query = "Prove the harmonic series diverges"
        await planner.plan(query)
        call_kwargs = mock_provider.complete.call_args
        # The query should appear in the positional prompt argument
        prompt_arg = call_kwargs[0][0] if call_kwargs[0] else call_kwargs[1].get("prompt", "")
        assert query in prompt_arg


class TestParseResponse:
    def test_parse_plain_json(self, planner: Planner, fixture_content: str) -> None:
        data = planner._parse_response(fixture_content)
        assert data["topic"] == "harmonic-series-divergence"

    def test_parse_with_json_fence(self, planner: Planner, fixture_content: str) -> None:
        fenced = f"```json\n{fixture_content}\n```"
        data = planner._parse_response(fenced)
        assert data["topic"] == "harmonic-series-divergence"

    def test_parse_with_plain_fence(self, planner: Planner, fixture_content: str) -> None:
        fenced = f"```\n{fixture_content}\n```"
        data = planner._parse_response(fenced)
        assert data["topic"] == "harmonic-series-divergence"

    def test_parse_invalid_json_raises_value_error(self, planner: Planner) -> None:
        with pytest.raises(ValueError, match="Failed to parse planner JSON response"):
            planner._parse_response("not valid json {{{")
