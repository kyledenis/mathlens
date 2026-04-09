"""Unit tests for the Verifier pipeline stage."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from mathlens.models import PipelineMode, VerificationStatus
from mathlens.pipeline.verifier import Verifier
from mathlens.providers.base import LLMResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LEAN_STUB = "import Mathlib\n\ntheorem trivial : True := trivial\n"


def make_provider(content: str = LEAN_STUB) -> AsyncMock:
    """Return a mock LLMProvider whose complete() returns *content*."""
    provider = AsyncMock()
    provider.complete = AsyncMock(
        return_value=LLMResponse(content=content, model="mock", usage={})
    )
    return provider


def make_verifier(tmp_path: Path, provider=None) -> Verifier:
    if provider is None:
        provider = make_provider()
    return Verifier(
        provider=provider,
        workspace_dir=tmp_path,
        explore_timeout=600,
        deep_timeout=1800,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_success(tmp_path: Path) -> None:
    verifier = make_verifier(tmp_path)
    with patch.object(Verifier, "_run_lean", new=AsyncMock(return_value=(0, "No errors", ""))):
        result = await verifier.verify(["theorem foo : True := trivial"], PipelineMode.explore)

    assert result.status == VerificationStatus.verified
    assert result.proof_path is not None and result.proof_path.exists()
    assert result.should_halt is False
    assert result.duration_seconds >= 0.0


@pytest.mark.asyncio
async def test_verify_lean_rejects(tmp_path: Path) -> None:
    verifier = make_verifier(tmp_path)
    stderr = "type mismatch\nexpected type 'Nat'\ngot 'String'"
    with patch.object(Verifier, "_run_lean", new=AsyncMock(return_value=(1, "", stderr))):
        result = await verifier.verify(["theorem bad : 1 = 2 := rfl"], PipelineMode.explore)

    assert result.status == VerificationStatus.refuted
    assert result.should_halt is True
    assert result.failure_reason is not None


@pytest.mark.asyncio
async def test_verify_timeout(tmp_path: Path) -> None:
    verifier = make_verifier(tmp_path)
    with patch.object(Verifier, "_run_lean", new=AsyncMock(side_effect=TimeoutError)):
        result = await verifier.verify(["theorem slow : True := by decide"], PipelineMode.explore)

    assert result.status == VerificationStatus.unverifiable
    assert result.failure_reason is not None
    assert "timeout" in result.failure_reason.lower()


@pytest.mark.asyncio
async def test_verify_lean_not_installed(tmp_path: Path) -> None:
    verifier = make_verifier(tmp_path)
    with patch.object(Verifier, "_run_lean", new=AsyncMock(side_effect=FileNotFoundError)):
        result = await verifier.verify(["theorem foo : True := trivial"], PipelineMode.explore)

    assert result.status == VerificationStatus.skipped
    assert result.failure_reason is not None
    assert "not installed" in result.failure_reason.lower()


@pytest.mark.asyncio
async def test_verify_saves_proof_file(tmp_path: Path) -> None:
    verifier = make_verifier(tmp_path)
    with patch.object(Verifier, "_run_lean", new=AsyncMock(return_value=(0, "", ""))):
        result = await verifier.verify(["theorem foo : True := trivial"], PipelineMode.explore)

    assert result.proof_path is not None
    assert result.proof_path.exists()
    assert result.proof_path.read_text(encoding="utf-8").strip() != ""


@pytest.mark.asyncio
async def test_explore_vs_deep_timeout(tmp_path: Path) -> None:
    verifier = make_verifier(tmp_path)
    assert verifier._timeout_for(PipelineMode.explore) == 600
    assert verifier._timeout_for(PipelineMode.deep) == 1800


@pytest.mark.asyncio
async def test_skip_when_no_statements(tmp_path: Path) -> None:
    verifier = make_verifier(tmp_path)
    result = await verifier.verify([], PipelineMode.explore)

    assert result.status == VerificationStatus.skipped
    assert result.failure_reason == "No theorem statements to verify"
