"""Verifier pipeline stage — formalises theorem statements with Lean 4."""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Optional

from mathlens.models import PipelineMode, VerificationResult, VerificationStatus
from mathlens.pipeline.response_cleaner import clean_code_response
from mathlens.pipeline.validation import validate_lean
from mathlens.workspace.atomic import atomic_write_text
from mathlens.workspace.lean_project import LeanProject, LeanREPL
from mathlens.providers.base import LLMProvider

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

FORMALIZE_SYSTEM = """\
You are an expert Lean 4 / Mathlib proof assistant.

Given one or more mathematical theorem statements, produce a single valid Lean 4
source file that:
1. Begins with the necessary Mathlib imports (e.g. `import Mathlib`).
2. States each theorem using `theorem` or `lemma`.
3. Provides a complete proof when possible.
4. Uses `sorry` (with an inline comment explaining the gap) wherever a proof
   cannot be completed.

Respond with ONLY the Lean 4 source -- no prose, no markdown fences.
"""

# ---------------------------------------------------------------------------
# Verifier
# ---------------------------------------------------------------------------


class Verifier:
    """Pipeline stage that verifies theorem statements via Lean 4."""

    def __init__(
        self,
        provider: LLMProvider,
        workspace_dir: Path,
        explore_timeout: int = 60,
        deep_timeout: int = 300,
    ) -> None:
        self._provider = provider
        self._workspace_dir = Path(workspace_dir)
        self._explore_timeout = explore_timeout
        self._deep_timeout = deep_timeout
        self._last_reasoning: str = ""
        self._lean_project = LeanProject(self._workspace_dir / "lean-project")
        self._repl = LeanREPL(project_dir=self._lean_project.path, idle_timeout=120)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def _timeout_for(self, mode: PipelineMode) -> int:
        """Return the Lean subprocess timeout in seconds for *mode*."""
        if mode == PipelineMode.deep:
            return self._deep_timeout
        return self._explore_timeout

    async def verify(
        self,
        statements: list[str],
        mode: PipelineMode,
        workspace_dir: Optional[Path] = None,
    ) -> VerificationResult:
        """Attempt to verify *statements* using Lean 4."""
        if not statements:
            return VerificationResult(
                status=VerificationStatus.skipped,
                lean_output="",
                failure_reason="No theorem statements to verify",
                duration_seconds=0.0,
            )

        target_dir = workspace_dir or self._workspace_dir
        start = time.monotonic()

        # Check prerequisites
        if shutil.which("lean") is None:
            return VerificationResult(
                status=VerificationStatus.skipped,
                lean_output="",
                failure_reason="Lean 4 is not installed",
                duration_seconds=0.0,
            )

        if not self._lean_project.is_ready():
            return VerificationResult(
                status=VerificationStatus.skipped,
                lean_output="",
                failure_reason=(
                    "Mathlib not set up. "
                    "Run `mathlens doctor --install` to download Mathlib."
                ),
                duration_seconds=0.0,
            )

        # Ask the LLM to produce Lean 4 source.
        prompt = "\n\n".join(statements)
        response = await self._provider.complete(
            prompt=prompt,
            system=FORMALIZE_SYSTEM,
            temperature=0.0,
        )
        cleaned = clean_code_response(response.content, "lean")
        lean_code = cleaned.code
        self._last_reasoning = cleaned.reasoning

        # Validate — retry once if the output looks like prose, not code.
        valid, error = validate_lean(lean_code)
        if not valid:
            retry_prompt = (
                f"Your previous response was not valid Lean 4 code.\n"
                f"Error: {error}\n\n"
                f"Please respond with ONLY valid Lean 4 source code. "
                f"No prose, no markdown fences, no explanations.\n\n"
                f"{prompt}"
            )
            response = await self._provider.complete(
                prompt=retry_prompt,
                system=FORMALIZE_SYSTEM,
                temperature=0.0,
            )
            cleaned = clean_code_response(response.content, "lean")
            lean_code = cleaned.code
            if cleaned.reasoning:
                self._last_reasoning += "\n\n" + cleaned.reasoning

        # Save proof to the exploration workspace for archival
        proof_path = target_dir / "proof.lean"
        target_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_text(proof_path, lean_code)

        # Typecheck via the shared Lake project (has Mathlib available)
        timeout = self._timeout_for(mode)

        try:
            returncode, stdout, stderr = await self._repl.check(
                lean_code, timeout=timeout,
            )
        except TimeoutError:
            duration = time.monotonic() - start
            return VerificationResult(
                status=VerificationStatus.unverifiable,
                proof_path=proof_path,
                lean_output="",
                failure_reason=f"Proof timeout after {timeout}s",
                duration_seconds=duration,
            )

        duration = time.monotonic() - start
        lean_output = stdout + stderr

        if returncode == 0:
            return VerificationResult(
                status=VerificationStatus.verified,
                proof_path=proof_path,
                lean_output=lean_output,
                duration_seconds=duration,
            )

        # Non-zero return — decide between REFUTED and UNVERIFIABLE.
        refute_markers = ("type mismatch", "failed to synthesize", "unknown identifier")
        if any(marker in stderr for marker in refute_markers):
            status = VerificationStatus.refuted
        else:
            status = VerificationStatus.unverifiable

        return VerificationResult(
            status=status,
            proof_path=proof_path,
            lean_output=lean_output,
            failure_reason=self._extract_failure_reason(stderr),
            mathlib_gaps=self._detect_mathlib_gaps(stderr),
            duration_seconds=duration,
        )

    async def cleanup(self) -> None:
        """Stop the Lean REPL. Called when the pipeline finishes."""
        await self._repl.stop()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_lean_code(content: str) -> str:
        """Extract clean Lean code from LLM output."""
        return clean_code_response(content, "lean").code

    @staticmethod
    def _extract_failure_reason(stderr: str) -> Optional[str]:
        """Return the first non-empty line of *stderr*, or None."""
        for line in stderr.splitlines():
            if line.strip():
                return line.strip()
        return None

    @staticmethod
    def _detect_mathlib_gaps(stderr: str) -> list[str]:
        """Return lines in *stderr* that contain ``unknown identifier``."""
        return [
            line.strip()
            for line in stderr.splitlines()
            if "unknown identifier" in line
        ]
