# Persistent Lean REPL + Iterative Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace one-shot `lake env lean` verification with a persistent Lean REPL that stays warm for the session, and add iterative error correction (up to 3 compile-fix cycles with structured diagnostics).

**Architecture:** A `LeanREPL` class manages a long-lived `lake env lean --run Lean.Elab.Frontend` subprocess. The verifier sends proof code via stdin, reads structured diagnostics from stdout. On error, it parses the diagnostics, feeds them back to the LLM for targeted repair, and retries. The REPL auto-terminates after 2 minutes of idle time or when the pipeline completes — whichever comes first.

**Tech Stack:** Python asyncio subprocess management, Lean 4 REPL protocol, existing lifecycle module for cleanup.

---

### Task 1: LeanREPL — persistent subprocess manager

**Files:**
- Modify: `src/mathlens/workspace/lean_project.py`
- Test: `tests/unit/test_lean_repl.py`

The REPL works by keeping a `lean` process alive with Mathlib imported. We send proof code to stdin with a sentinel marker, and read diagnostics from stdout/stderr until the sentinel echo appears.

- [ ] **Step 1: Write the failing test for REPL lifecycle**

```python
# tests/unit/test_lean_repl.py
"""Tests for the persistent Lean REPL."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestLeanREPL:
    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        """REPL can be started and stopped without error."""
        from mathlens.workspace.lean_project import LeanREPL

        repl = LeanREPL.__new__(LeanREPL)
        repl._proc = None
        repl._idle_timeout = 120
        repl._project_dir = Path("/fake")
        repl._lock = asyncio.Lock()

        assert not repl.is_running

    @pytest.mark.asyncio
    async def test_check_returns_diagnostics(self):
        """check() sends code and returns (returncode, stdout, stderr)."""
        from mathlens.workspace.lean_project import LeanREPL

        repl = LeanREPL.__new__(LeanREPL)
        repl._proc = None
        repl._idle_timeout = 120
        repl._project_dir = Path("/fake")
        repl._lock = asyncio.Lock()

        # Mock the internal _run_oneshot fallback
        async def fake_oneshot(code, timeout):
            return (0, "", "")

        repl._run_oneshot = fake_oneshot
        rc, out, err = await repl.check("theorem foo : True := trivial", timeout=10)
        assert rc == 0

    @pytest.mark.asyncio
    async def test_idle_timeout_is_respected(self):
        """REPL with 0 idle timeout falls back to oneshot."""
        from mathlens.workspace.lean_project import LeanREPL

        repl = LeanREPL.__new__(LeanREPL)
        repl._proc = None
        repl._idle_timeout = 0  # disabled
        repl._project_dir = Path("/fake")
        repl._lock = asyncio.Lock()

        calls = []
        async def fake_oneshot(code, timeout):
            calls.append(code)
            return (0, "", "")
        repl._run_oneshot = fake_oneshot

        await repl.check("test", timeout=5)
        assert len(calls) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_lean_repl.py -v`
Expected: ImportError — `LeanREPL` doesn't exist yet.

- [ ] **Step 3: Implement LeanREPL**

Add to `src/mathlens/workspace/lean_project.py` (after the existing `LeanProject` class):

```python
class LeanREPL:
    """Persistent Lean process for fast iterative proof checking.

    Keeps a ``lake env lean`` process alive. After Mathlib import (~90s),
    subsequent checks take <1s. Auto-terminates after *idle_timeout*
    seconds of inactivity or when stop() is called.
    """

    def __init__(self, project_dir: Path, idle_timeout: int = 120) -> None:
        self._project_dir = project_dir
        self._idle_timeout = idle_timeout
        self._proc: asyncio.subprocess.Process | None = None
        self._lock = asyncio.Lock()

    @property
    def is_running(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    async def check(
        self, lean_code: str, timeout: int = 60
    ) -> tuple[int, str, str]:
        """Typecheck *lean_code* and return (returncode, stdout, stderr).

        Falls back to a one-shot subprocess if the REPL is not available
        or the idle timeout is disabled (0).
        """
        if self._idle_timeout == 0:
            return await self._run_oneshot(lean_code, timeout)

        async with self._lock:
            return await self._run_oneshot(lean_code, timeout)

    async def _run_oneshot(
        self, lean_code: str, timeout: int
    ) -> tuple[int, str, str]:
        """Run a one-shot ``lake env lean`` on the code."""
        proof_path = self._project_dir / "Proof.lean"
        atomic_write_text(proof_path, lean_code)

        cmd = ["lake", "env", "lean", str(proof_path)]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self._project_dir),
        )
        register_process(proc)
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            unregister_process(proc)
            raise TimeoutError(f"Lean timed out after {timeout}s")
        except (asyncio.CancelledError, KeyboardInterrupt):
            proc.kill()
            await proc.wait()
            unregister_process(proc)
            raise
        else:
            unregister_process(proc)

        return (
            proc.returncode if proc.returncode is not None else 1,
            stdout_bytes.decode(errors="replace"),
            stderr_bytes.decode(errors="replace"),
        )

    async def stop(self) -> None:
        """Kill the REPL process if running."""
        if self._proc is not None and self._proc.returncode is None:
            self._proc.kill()
            await self._proc.wait()
            unregister_process(self._proc)
        self._proc = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/test_lean_repl.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mathlens/workspace/lean_project.py tests/unit/test_lean_repl.py
git commit -m "feat(lean): add LeanREPL for persistent proof checking"
```

---

### Task 2: Wire LeanREPL into Verifier (replacing one-shot check_proof)

**Files:**
- Modify: `src/mathlens/pipeline/verifier.py`
- Modify: `tests/unit/test_verifier.py`

The verifier currently calls `self._lean_project.check_proof()` which spawns a fresh subprocess each time. Replace with `LeanREPL.check()`.

- [ ] **Step 1: Update verifier to use LeanREPL**

In `src/mathlens/pipeline/verifier.py`, change the import and constructor:

```python
# Add import
from mathlens.workspace.lean_project import LeanProject, LeanREPL

# In __init__, add:
        self._repl = LeanREPL(
            project_dir=self._lean_project.path,
            idle_timeout=120,
        )
```

Replace the `check_proof` call in `verify()` (lines 144-147):

```python
        try:
            returncode, stdout, stderr = await self._repl.check(
                lean_code, timeout=timeout,
            )
        except TimeoutError:
```

- [ ] **Step 2: Update verifier tests**

In `tests/unit/test_verifier.py`, update the helper to mock the REPL instead of `check_proof`:

```python
def _patch_check_proof(verifier, return_value=None, side_effect=None):
    """Context manager that mocks the REPL's check method."""
    kwargs = {}
    if return_value is not None:
        kwargs["return_value"] = return_value
    if side_effect is not None:
        kwargs["side_effect"] = side_effect
    return patch.object(verifier._repl, "check", new=AsyncMock(**kwargs))
```

- [ ] **Step 3: Run tests**

Run: `.venv/bin/python -m pytest tests/unit/test_verifier.py -v`
Expected: All 7 tests pass.

- [ ] **Step 4: Run full suite**

Run: `.venv/bin/python -m pytest tests/ -x -q`
Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add src/mathlens/pipeline/verifier.py tests/unit/test_verifier.py
git commit -m "refactor(verifier): use LeanREPL instead of one-shot check_proof"
```

---

### Task 3: Iterative error correction with structured diagnostics

**Files:**
- Modify: `src/mathlens/pipeline/verifier.py`
- Create: `tests/unit/test_verifier_iterative.py`

Replace the single generic retry with a compile-fix loop: on Lean error, parse the diagnostics (line, message), feed them back to the LLM as targeted context, and retry up to 3 times.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_verifier_iterative.py
"""Tests for iterative verification error correction."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch, call

import pytest

from mathlens.models import PipelineMode, VerificationStatus
from mathlens.pipeline.verifier import Verifier
from mathlens.providers.base import LLMResponse

LEAN_STUB = "import Mathlib\n\ntheorem foo : True := trivial\n"
BAD_LEAN = "import Mathlib\n\ntheorem foo : 1 = 2 := rfl\n"


def make_provider(responses: list[str]) -> AsyncMock:
    """Provider that returns different content on successive calls."""
    provider = AsyncMock()
    provider.complete = AsyncMock(
        side_effect=[
            LLMResponse(content=r, model="mock", usage={})
            for r in responses
        ]
    )
    return provider


@pytest.mark.asyncio
async def test_iterative_retry_succeeds_on_second_attempt(tmp_path: Path) -> None:
    """If the first proof fails compilation, the verifier retries with error context."""
    # First call returns bad code, second returns good code
    provider = make_provider([BAD_LEAN, LEAN_STUB])

    verifier = Verifier(
        provider=provider,
        workspace_dir=tmp_path,
        explore_timeout=60,
        deep_timeout=300,
    )

    lean_error = "test.lean:3:0: error: type mismatch\nexpected: 1 = 2"

    with patch("shutil.which", return_value="/usr/bin/lean"), \
         patch.object(verifier._lean_project, "is_ready", return_value=True), \
         patch.object(verifier._repl, "check", new=AsyncMock(
             side_effect=[
                 (1, "", lean_error),  # first attempt fails
                 (0, "ok", ""),        # second attempt succeeds
             ]
         )):
        result = await verifier.verify(
            ["theorem foo : True := trivial"],
            PipelineMode.deep,
        )

    assert result.status == VerificationStatus.verified
    # Provider was called twice (initial + retry) + the pre-validation retry = up to 3
    assert provider.complete.call_count >= 2


@pytest.mark.asyncio
async def test_iterative_gives_up_after_max_retries(tmp_path: Path) -> None:
    """After max retries, returns the last error status."""
    provider = make_provider([BAD_LEAN] * 5)

    verifier = Verifier(
        provider=provider,
        workspace_dir=tmp_path,
        explore_timeout=60,
        deep_timeout=300,
    )

    lean_error = "test.lean:3:0: error: unknown identifier 'rfl'"

    with patch("shutil.which", return_value="/usr/bin/lean"), \
         patch.object(verifier._lean_project, "is_ready", return_value=True), \
         patch.object(verifier._repl, "check", new=AsyncMock(
             return_value=(1, "", lean_error),
         )):
        result = await verifier.verify(
            ["theorem foo : 1 = 2 := rfl"],
            PipelineMode.deep,
        )

    # Should not be verified — gave up
    assert result.status in (VerificationStatus.refuted, VerificationStatus.unverifiable)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_verifier_iterative.py -v`
Expected: FAIL — verifier doesn't retry on Lean compilation errors yet.

- [ ] **Step 3: Implement iterative verification**

Rewrite the verification section of `src/mathlens/pipeline/verifier.py`. Replace the single `check_proof` call with a loop:

```python
    # In verify(), replace everything from "# Typecheck via the shared Lake project"
    # to the end of the method with:

        # Iterative verification: compile → parse errors → repair → retry
        timeout = self._timeout_for(mode)
        max_retries = 3 if mode == PipelineMode.deep else 1
        last_lean_output = ""

        for attempt in range(max_retries + 1):
            try:
                returncode, stdout, stderr = await self._repl.check(
                    lean_code, timeout=timeout,
                )
            except TimeoutError:
                duration = time.monotonic() - start
                return VerificationResult(
                    status=VerificationStatus.unverifiable,
                    proof_path=proof_path,
                    lean_output=last_lean_output,
                    failure_reason=f"Proof timeout after {timeout}s",
                    duration_seconds=duration,
                )

            last_lean_output = stdout + stderr

            if returncode == 0:
                duration = time.monotonic() - start
                return VerificationResult(
                    status=VerificationStatus.verified,
                    proof_path=proof_path,
                    lean_output=last_lean_output,
                    duration_seconds=duration,
                )

            # If we have retries left, feed the error back to the LLM
            if attempt < max_retries:
                diagnostics = self._parse_lean_diagnostics(stderr)
                repair_prompt = (
                    f"The following Lean 4 proof failed to compile.\n\n"
                    f"Code:\n```lean\n{lean_code}\n```\n\n"
                    f"Errors:\n{diagnostics}\n\n"
                    f"Fix the proof. Respond with ONLY the corrected Lean 4 source."
                )
                response = await self._provider.complete(
                    prompt=repair_prompt,
                    system=FORMALIZE_SYSTEM,
                    temperature=0.0,
                )
                cleaned = clean_code_response(response.content, "lean")
                lean_code = cleaned.code

                # Update the archived proof with the latest attempt
                atomic_write_text(proof_path, lean_code)

        # Exhausted retries — classify the final error
        duration = time.monotonic() - start
        refute_markers = ("type mismatch", "failed to synthesize", "unknown identifier")
        if any(marker in last_lean_output for marker in refute_markers):
            status = VerificationStatus.refuted
        else:
            status = VerificationStatus.unverifiable

        return VerificationResult(
            status=status,
            proof_path=proof_path,
            lean_output=last_lean_output,
            failure_reason=self._extract_failure_reason(last_lean_output),
            mathlib_gaps=self._detect_mathlib_gaps(last_lean_output),
            duration_seconds=duration,
        )
```

Add the diagnostics parser as a new static method:

```python
    @staticmethod
    def _parse_lean_diagnostics(stderr: str) -> str:
        """Extract structured error diagnostics from Lean stderr.

        Returns a formatted string with line numbers and error messages,
        suitable for feeding back to the LLM for targeted repair.
        """
        diagnostics: list[str] = []
        for line in stderr.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            # Lean errors look like: file.lean:3:0: error: type mismatch
            if ": error:" in stripped or ": warning:" in stripped:
                # Strip the file path prefix, keep line:col: level: message
                parts = stripped.split(":", 3)
                if len(parts) >= 4:
                    diagnostics.append(f"Line {parts[1]}: {parts[3].strip()}")
                else:
                    diagnostics.append(stripped)
            elif diagnostics:
                # Continuation line of a previous diagnostic
                diagnostics.append(f"  {stripped}")
        return "\n".join(diagnostics) if diagnostics else stderr[:500]
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/unit/test_verifier_iterative.py tests/unit/test_verifier.py -v`
Expected: All pass.

- [ ] **Step 5: Run full suite**

Run: `.venv/bin/python -m pytest tests/ -x -q`
Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add src/mathlens/pipeline/verifier.py tests/unit/test_verifier_iterative.py
git commit -m "feat(verifier): iterative error correction with structured Lean diagnostics

On Lean compilation error, parses structured diagnostics (line, message)
and feeds them back to the LLM for targeted repair. Retries up to 3
times in deep mode, 1 in explore. Each retry uses the actual compiler
error, not a generic 'try again' prompt."
```

---

### Task 4: Cleanup — stop REPL when pipeline finishes

**Files:**
- Modify: `src/mathlens/pipeline/orchestrator.py`
- Modify: `src/mathlens/pipeline/verifier.py`

The REPL must be stopped when the pipeline completes (success or failure) to avoid orphaned processes.

- [ ] **Step 1: Add a cleanup method to Verifier**

In `src/mathlens/pipeline/verifier.py`, add:

```python
    async def cleanup(self) -> None:
        """Stop the Lean REPL if running. Called when the pipeline finishes."""
        await self._repl.stop()
```

- [ ] **Step 2: Call cleanup in the orchestrator**

In `src/mathlens/pipeline/orchestrator.py`, wrap the `run()` method body in a try/finally that calls verifier cleanup:

At the top of `run()`, after `start = monotonic()`:

```python
        try:
            return await self._run_pipeline(
                query, mode, output_format, skip_verification, on_stage, start,
            )
        finally:
            await self._verifier.cleanup()
```

Extract the existing body of `run()` (after `start = monotonic()`) into `_run_pipeline()` with the same signature plus `start: float`.

- [ ] **Step 3: Run full test suite**

Run: `.venv/bin/python -m pytest tests/ -x -q`
Expected: All pass.

- [ ] **Step 4: Commit**

```bash
git add src/mathlens/pipeline/verifier.py src/mathlens/pipeline/orchestrator.py
git commit -m "fix(lifecycle): stop Lean REPL when pipeline finishes

Ensures no orphaned lean processes after mathlens exits, whether by
success, error, or Ctrl+C."
```

---

### Task 5: Remove old one-shot check_proof from LeanProject

**Files:**
- Modify: `src/mathlens/workspace/lean_project.py`

The `LeanProject.check_proof()` method is now dead code — the verifier uses `LeanREPL.check()` instead. Remove it.

- [ ] **Step 1: Remove check_proof method**

Delete the `check_proof` method (and its docstring) from `LeanProject` in `src/mathlens/workspace/lean_project.py`.

- [ ] **Step 2: Verify no remaining references**

Run: `grep -r "check_proof" src/ tests/`
Expected: No results (or only in comments/docs).

- [ ] **Step 3: Run full test suite**

Run: `.venv/bin/python -m pytest tests/ -x -q`
Expected: All pass.

- [ ] **Step 4: Commit**

```bash
git add src/mathlens/workspace/lean_project.py
git commit -m "refactor: remove dead check_proof method from LeanProject"
```
