"""Verifier pipeline stage — formalises theorem statements with Lean 4."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Optional

from mathlens.models import PipelineMode, VerificationResult, VerificationStatus
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
    ) -> VerificationResult:
        """Attempt to verify *statements* using Lean 4."""
        if not statements:
            return VerificationResult(
                status=VerificationStatus.skipped,
                lean_output="",
                failure_reason="No theorem statements to verify",
                duration_seconds=0.0,
            )

        start = time.monotonic()

        # Ask the LLM to produce Lean 4 source.
        prompt = "\n\n".join(statements)
        response = await self._provider.complete(
            prompt=prompt,
            system=FORMALIZE_SYSTEM,
            temperature=0.0,
        )
        lean_code = self._extract_lean_code(response.content)

        # Persist to disk so Lean can be invoked on it.
        proof_path = self._workspace_dir / "proof.lean"
        self._workspace_dir.mkdir(parents=True, exist_ok=True)
        proof_path.write_text(lean_code, encoding="utf-8")

        timeout = self._timeout_for(mode)

        try:
            returncode, stdout, stderr = await self._run_lean(proof_path, timeout)
        except FileNotFoundError:
            duration = time.monotonic() - start
            return VerificationResult(
                status=VerificationStatus.skipped,
                proof_path=proof_path,
                lean_output="",
                failure_reason="Lean 4 is not installed",
                duration_seconds=duration,
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

        # Non-zero return -- decide between REFUTED and UNVERIFIABLE.
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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_lean(
        self,
        path: Path,
        timeout: int,
    ) -> tuple[int, str, str]:
        """Run ``lean <path>`` and return (returncode, stdout, stderr)."""
        proc = await asyncio.create_subprocess_exec(
            "lean",
            str(path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )
        except asyncio.TimeoutError as exc:
            proc.kill()
            await proc.communicate()
            raise TimeoutError from exc

        return (
            proc.returncode if proc.returncode is not None else 1,
            stdout_bytes.decode(errors="replace"),
            stderr_bytes.decode(errors="replace"),
        )

    @staticmethod
    def _extract_lean_code(content: str) -> str:
        """Strip markdown fences from *content* if present."""
        lines = content.splitlines()
        result: list[str] = []
        in_fence = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("```"):
                in_fence = not in_fence
                continue
            result.append(line)
        return "\n".join(result)

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
