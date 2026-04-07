"""Unit tests for the Summarizer pipeline stage."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from mathlens.models import (
    ExplorationPlan,
    Summary,
    VerificationResult,
    VerificationStatus,
)
from mathlens.pipeline.summarizer import Summarizer
from mathlens.providers.base import LLMResponse, ProviderCapabilities, Tier


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MOCK_RESPONSE_JSON = json.dumps(
    {
        "explanation": "The harmonic series diverges because its partial sums grow without bound.",
        "key_insights": [
            "Grouping terms shows each group sums to at least 1/2",
            "The series grows logarithmically",
        ],
        "prerequisites": ["sequences-basics"],
        "further_reading": ["p-series-convergence"],
    }
)


@pytest.fixture()
def mock_provider() -> MagicMock:
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
        return_value=LLMResponse(content=MOCK_RESPONSE_JSON, model="mock-model")
    )
    return provider


@pytest.fixture()
def summarizer(mock_provider: MagicMock, tmp_workspace: Path) -> Summarizer:
    return Summarizer(mock_provider, tmp_workspace)


@pytest.fixture()
def sample_verification_unverifiable() -> VerificationResult:
    return VerificationResult(
        status=VerificationStatus.unverifiable,
        lean_output="No Lean proof found.",
        failure_reason="No applicable Mathlib lemma",
        duration_seconds=2.1,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSummarize:
    @pytest.mark.asyncio
    async def test_summarize_produces_summary(
        self,
        summarizer: Summarizer,
        sample_plan: ExplorationPlan,
        sample_verification_verified: VerificationResult,
    ) -> None:
        result = await summarizer.summarize(sample_plan, sample_verification_verified)
        assert isinstance(result, Summary)
        assert "harmonic series" in result.explanation.lower()
        assert len(result.key_insights) == 2

    @pytest.mark.asyncio
    async def test_summary_saved_to_workspace(
        self,
        summarizer: Summarizer,
        sample_plan: ExplorationPlan,
        sample_verification_verified: VerificationResult,
    ) -> None:
        result = await summarizer.summarize(sample_plan, sample_verification_verified)
        assert result.path is not None
        assert result.path.is_file()

    @pytest.mark.asyncio
    async def test_summary_includes_verification_context(
        self,
        mock_provider: MagicMock,
        tmp_workspace: Path,
        sample_plan: ExplorationPlan,
        sample_verification_unverifiable: VerificationResult,
    ) -> None:
        summarizer = Summarizer(mock_provider, tmp_workspace)
        await summarizer.summarize(sample_plan, sample_verification_unverifiable)
        call_kwargs = mock_provider.complete.call_args
        prompt_arg = call_kwargs[0][0] if call_kwargs[0] else call_kwargs[1].get("prompt", "")
        assert "unverifiable" in prompt_arg.lower()


class TestParseResponse:
    def test_parse_plain_json(self, summarizer: Summarizer) -> None:
        data = summarizer._parse_response(MOCK_RESPONSE_JSON)
        assert "harmonic series" in data["explanation"].lower()
        assert len(data["key_insights"]) == 2

    def test_parse_with_json_fence(self, summarizer: Summarizer) -> None:
        fenced = f"```json\n{MOCK_RESPONSE_JSON}\n```"
        data = summarizer._parse_response(fenced)
        assert "explanation" in data

    def test_parse_with_plain_fence(self, summarizer: Summarizer) -> None:
        fenced = f"```\n{MOCK_RESPONSE_JSON}\n```"
        data = summarizer._parse_response(fenced)
        assert "explanation" in data

    def test_parse_invalid_json_falls_back_to_raw(self, summarizer: Summarizer) -> None:
        raw = "This is not JSON at all."
        data = summarizer._parse_response(raw)
        assert data["explanation"] == raw
        assert data["key_insights"] == []


class TestFormatMarkdown:
    def test_format_markdown_includes_topic(
        self, summarizer: Summarizer, sample_plan: ExplorationPlan
    ) -> None:
        data = json.loads(MOCK_RESPONSE_JSON)
        md = summarizer._format_markdown(data, sample_plan)
        assert "Harmonic Series Divergence" in md

    def test_format_markdown_includes_key_insights(
        self, summarizer: Summarizer, sample_plan: ExplorationPlan
    ) -> None:
        data = json.loads(MOCK_RESPONSE_JSON)
        md = summarizer._format_markdown(data, sample_plan)
        assert "Key Insights" in md
        assert "Grouping terms" in md

    def test_format_markdown_includes_prerequisites(
        self, summarizer: Summarizer, sample_plan: ExplorationPlan
    ) -> None:
        data = json.loads(MOCK_RESPONSE_JSON)
        md = summarizer._format_markdown(data, sample_plan)
        assert "Prerequisites" in md
        assert "sequences-basics" in md

    def test_format_markdown_includes_further_reading(
        self, summarizer: Summarizer, sample_plan: ExplorationPlan
    ) -> None:
        data = json.loads(MOCK_RESPONSE_JSON)
        md = summarizer._format_markdown(data, sample_plan)
        assert "Further Reading" in md
        assert "p-series-convergence" in md
