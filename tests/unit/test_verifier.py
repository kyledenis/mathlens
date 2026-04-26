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


def make_provider(content: str = LEAN_STUB, responses: list[str] | None = None) -> AsyncMock:
    """Return a mock LLMProvider whose complete() returns *content*.

    If *responses* is given, each call returns the next response in order
    (cycling the last one if more calls are made than responses provided).
    """
    provider = AsyncMock()
    if responses is not None:
        provider.complete = AsyncMock(
            side_effect=[
                LLMResponse(content=r, model="mock", usage={})
                for r in responses
            ]
        )
    else:
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
        explore_timeout=60,
        deep_timeout=300,
    )


def _patch_ready_verifier(verifier):
    """Context manager that makes the verifier's LeanProject appear ready."""
    return patch.object(verifier._lean_project, "is_ready", return_value=True)


def _patch_check_proof(verifier, return_value=None, side_effect=None):
    """Context manager that mocks the REPL's check method."""
    kwargs = {}
    if return_value is not None:
        kwargs["return_value"] = return_value
    if side_effect is not None:
        kwargs["side_effect"] = side_effect
    return patch.object(verifier._repl, "check", new=AsyncMock(**kwargs))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_success(tmp_path: Path) -> None:
    verifier = make_verifier(tmp_path)
    with patch("shutil.which", return_value="/usr/bin/lean"), \
         _patch_ready_verifier(verifier), \
         _patch_check_proof(verifier, return_value=(0, "No errors", "")):
        result = await verifier.verify(["theorem foo : True := trivial"], PipelineMode.explore)

    assert result.status == VerificationStatus.verified
    assert result.proof_path is not None and result.proof_path.exists()
    assert result.should_halt is False


@pytest.mark.asyncio
async def test_verify_lean_rejects(tmp_path: Path) -> None:
    # Explore mode: 1 initial + 1 retry = 2 LLM calls, both compilations fail
    provider = make_provider(responses=[LEAN_STUB, LEAN_STUB])
    verifier = make_verifier(tmp_path, provider=provider)
    stderr = "type mismatch\nexpected type 'Nat'\ngot 'String'"
    with patch("shutil.which", return_value="/usr/bin/lean"), \
         _patch_ready_verifier(verifier), \
         _patch_check_proof(verifier, return_value=(1, "", stderr)):
        result = await verifier.verify(["theorem bad : 1 = 2 := rfl"], PipelineMode.explore)

    assert result.status == VerificationStatus.refuted
    assert result.should_halt is True


@pytest.mark.asyncio
async def test_verify_timeout(tmp_path: Path) -> None:
    verifier = make_verifier(tmp_path)
    with patch("shutil.which", return_value="/usr/bin/lean"), \
         _patch_ready_verifier(verifier), \
         _patch_check_proof(verifier, side_effect=TimeoutError):
        result = await verifier.verify(["theorem slow : True := by decide"], PipelineMode.explore)

    assert result.status == VerificationStatus.unverifiable
    assert "timeout" in result.failure_reason.lower()


@pytest.mark.asyncio
async def test_verify_lean_not_installed(tmp_path: Path) -> None:
    verifier = make_verifier(tmp_path)
    with patch("shutil.which", return_value=None):
        result = await verifier.verify(["theorem foo : True := trivial"], PipelineMode.explore)

    assert result.status == VerificationStatus.skipped
    assert "not installed" in result.failure_reason.lower()


@pytest.mark.asyncio
async def test_verify_mathlib_not_ready(tmp_path: Path) -> None:
    verifier = make_verifier(tmp_path)
    with patch("shutil.which", return_value="/usr/bin/lean"), \
         patch.object(verifier._lean_project, "is_ready", return_value=False):
        result = await verifier.verify(["theorem foo : True := trivial"], PipelineMode.explore)

    assert result.status == VerificationStatus.skipped
    assert "mathlens doctor" in result.failure_reason.lower()


@pytest.mark.asyncio
async def test_explore_vs_deep_timeout(tmp_path: Path) -> None:
    verifier = make_verifier(tmp_path)
    assert verifier._timeout_for(PipelineMode.explore) == 60
    assert verifier._timeout_for(PipelineMode.deep) == 300


@pytest.mark.asyncio
async def test_skip_when_no_statements(tmp_path: Path) -> None:
    verifier = make_verifier(tmp_path)
    result = await verifier.verify([], PipelineMode.explore)
    assert result.status == VerificationStatus.skipped
