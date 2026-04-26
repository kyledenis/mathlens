"""Tests for iterative verification error correction."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from mathlens.models import PipelineMode, VerificationStatus
from mathlens.pipeline.verifier import Verifier
from mathlens.providers.base import LLMResponse

LEAN_STUB = "import Mathlib\n\ntheorem foo : True := trivial\n"
BAD_LEAN = "import Mathlib\n\ntheorem foo : 1 = 2 := rfl\n"


def _make_provider(responses: list[str]) -> AsyncMock:
    provider = AsyncMock()
    provider.complete = AsyncMock(
        side_effect=[
            LLMResponse(content=r, model="mock", usage={})
            for r in responses
        ]
    )
    return provider


@pytest.mark.asyncio
async def test_retry_succeeds_on_second_compile(tmp_path: Path) -> None:
    """First compile fails, LLM fixes it, second compile succeeds."""
    provider = _make_provider([BAD_LEAN, LEAN_STUB])
    verifier = Verifier(provider=provider, workspace_dir=tmp_path)

    lean_error = "Proof.lean:3:0: error: type mismatch\nexpected: 1 = 2"

    with patch("shutil.which", return_value="/usr/bin/lean"), \
         patch.object(verifier._lean_project, "is_ready", return_value=True), \
         patch.object(verifier._repl, "check", new=AsyncMock(
             side_effect=[
                 (1, "", lean_error),
                 (0, "ok", ""),
             ]
         )):
        result = await verifier.verify(
            ["theorem foo : True := trivial"],
            PipelineMode.deep,
        )

    assert result.status == VerificationStatus.verified
    assert provider.complete.call_count == 2


@pytest.mark.asyncio
async def test_exhausts_retries_in_explore(tmp_path: Path) -> None:
    """Explore mode gets 1 retry (2 attempts total), then gives up."""
    provider = _make_provider([BAD_LEAN, BAD_LEAN])
    verifier = Verifier(provider=provider, workspace_dir=tmp_path)

    lean_error = "Proof.lean:3:0: error: unknown identifier 'rfl'"

    with patch("shutil.which", return_value="/usr/bin/lean"), \
         patch.object(verifier._lean_project, "is_ready", return_value=True), \
         patch.object(verifier._repl, "check", new=AsyncMock(
             return_value=(1, "", lean_error),
         )):
        result = await verifier.verify(
            ["theorem foo : 1 = 2 := rfl"],
            PipelineMode.explore,
        )

    assert result.status in (VerificationStatus.refuted, VerificationStatus.unverifiable)
    # 1 initial + 1 retry = 2 LLM calls
    assert provider.complete.call_count == 2


@pytest.mark.asyncio
async def test_deep_gets_more_retries(tmp_path: Path) -> None:
    """Deep mode gets 3 retries (4 attempts total)."""
    provider = _make_provider([BAD_LEAN] * 4)
    verifier = Verifier(provider=provider, workspace_dir=tmp_path)

    with patch("shutil.which", return_value="/usr/bin/lean"), \
         patch.object(verifier._lean_project, "is_ready", return_value=True), \
         patch.object(verifier._repl, "check", new=AsyncMock(
             return_value=(1, "", "error: something wrong"),
         )):
        result = await verifier.verify(
            ["theorem foo : False := sorry"],
            PipelineMode.deep,
        )

    assert result.status == VerificationStatus.unverifiable
    # 1 initial + 3 retries = 4 LLM calls
    assert provider.complete.call_count == 4


@pytest.mark.asyncio
async def test_diagnostics_fed_back_to_llm(tmp_path: Path) -> None:
    """The repair prompt includes parsed diagnostics from stderr."""
    provider = _make_provider([BAD_LEAN, LEAN_STUB])
    verifier = Verifier(provider=provider, workspace_dir=tmp_path)

    lean_error = "Proof.lean:3:0: error: type mismatch\nhas type\n  Nat"

    with patch("shutil.which", return_value="/usr/bin/lean"), \
         patch.object(verifier._lean_project, "is_ready", return_value=True), \
         patch.object(verifier._repl, "check", new=AsyncMock(
             side_effect=[(1, "", lean_error), (0, "", "")]
         )):
        await verifier.verify(["theorem foo : True := trivial"], PipelineMode.deep)

    # Second call should contain the diagnostic
    repair_call = provider.complete.call_args_list[1]
    repair_prompt = repair_call.kwargs.get("prompt", repair_call.args[0] if repair_call.args else "")
    assert "type mismatch" in repair_prompt
