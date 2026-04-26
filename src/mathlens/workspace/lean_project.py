"""Shared Lake project for Lean 4 + Mathlib verification.

Manages a persistent Lake project in the mathlens workspace that all
verification runs share.  Mathlib is downloaded once (cached oleans from
the Mathlib CI server) and reused for every proof.

Typical lifecycle:
    project = LeanProject(workspace_root / "lean-project")
    if not project.is_ready():
        await project.setup()       # one-time: creates project, downloads Mathlib
    repl = LeanREPL(project.path)
    rc, stdout, stderr = await repl.check(lean_code, timeout=60)
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path

from mathlens.lifecycle import register_process, unregister_process
from mathlens.workspace.atomic import atomic_write_text

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lake project template files
# ---------------------------------------------------------------------------

_LAKEFILE = """\
import Lake
open Lake DSL

package «mathlens-proofs» where
  moreLeanArgs := #["-DautoImplicit=false"]

require mathlib from git
  "https://github.com/leanprover-community/mathlib4"

@[default_target]
lean_lib MathlensProofs where
  srcDir := "."
"""

_TOOLCHAIN_CMD = ["lean", "--version"]


# ---------------------------------------------------------------------------
# LeanProject
# ---------------------------------------------------------------------------


class LeanProject:
    """Manages a shared Lake project for Lean 4 / Mathlib verification."""

    def __init__(self, project_dir: Path) -> None:
        self._dir = project_dir

    @property
    def path(self) -> Path:
        return self._dir

    # ------------------------------------------------------------------
    # Status checks
    # ------------------------------------------------------------------

    def is_ready(self) -> bool:
        """Return True if the project exists and Mathlib oleans are built."""
        lakefile = self._dir / "lakefile.lean"
        lake_packages = self._dir / ".lake"
        return lakefile.exists() and lake_packages.exists()

    def has_lakefile(self) -> bool:
        return (self._dir / "lakefile.lean").exists()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    async def setup(self, timeout: int = 600) -> tuple[bool, str]:
        """Create the Lake project and download Mathlib.

        Returns ``(success, message)``.  This is a one-time operation that
        downloads cached Mathlib oleans (~2-4 GB).  Subsequent runs reuse
        the cache.
        """
        self._dir.mkdir(parents=True, exist_ok=True)

        # 1. Determine the Lean toolchain version
        lean_path = shutil.which("lean")
        if lean_path is None:
            return False, "Lean 4 is not installed"

        lake_path = shutil.which("lake")
        if lake_path is None:
            return False, "Lake is not installed (comes with elan)"

        # 2. Get toolchain string from lean --version
        try:
            proc = await asyncio.create_subprocess_exec(
                "lean", "--print-prefix",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            # Extract toolchain from the prefix path
            # e.g. /Users/x/.elan/toolchains/leanprover--lean4---v4.30.0-rc2
            prefix = stdout.decode().strip()
            toolchain_name = Path(prefix).name.replace("--", "/").replace("---", ":")
            # leanprover/lean4:v4.30.0-rc2
        except Exception:
            toolchain_name = None

        # 3. Write project files
        atomic_write_text(self._dir / "lakefile.lean", _LAKEFILE)

        if toolchain_name:
            atomic_write_text(self._dir / "lean-toolchain", toolchain_name + "\n")

        # Write a minimal lib file so Lake doesn't complain
        lib_file = self._dir / "MathlensProofs.lean"
        if not lib_file.exists():
            atomic_write_text(lib_file, "-- Placeholder for Lake\n")

        # 4. Run lake update to resolve dependencies
        logger.info("Running lake update in %s", self._dir)
        success, msg = await self._run_lake(["lake", "update"], timeout)
        if not success:
            return False, f"lake update failed: {msg}"

        # 5. Run lake build to download cached Mathlib oleans
        logger.info("Running lake build (downloading Mathlib cache)...")
        success, msg = await self._run_lake(
            ["lake", "exe", "cache", "get"], timeout,
        )
        if not success:
            # Fall back to lake build if cache get fails
            logger.info("Cache get failed, trying lake build...")
            success, msg = await self._run_lake(["lake", "build"], timeout)
            if not success:
                return False, f"lake build failed: {msg}"

        return True, "Mathlib project ready"


    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _run_lake(
        self, cmd: list[str], timeout: int
    ) -> tuple[bool, str]:
        """Run a Lake command in the project directory.

        Returns ``(success, output_or_error)``.
        """
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self._dir),
        )
        register_process(proc)
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            unregister_process(proc)
            return False, f"Timed out after {timeout}s"
        except (asyncio.CancelledError, KeyboardInterrupt):
            proc.kill()
            await proc.wait()
            unregister_process(proc)
            raise
        else:
            unregister_process(proc)

        output = stdout.decode(errors="replace") + stderr.decode(errors="replace")
        if proc.returncode != 0:
            return False, output
        return True, output


# ---------------------------------------------------------------------------
# LeanREPL
# ---------------------------------------------------------------------------


class LeanREPL:
    """Managed Lean proof checker with lifecycle cleanup.

    Currently delegates to one-shot ``lake env lean`` calls.
    The abstraction exists so a true persistent REPL can be
    added later without changing the verifier interface.
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
        """Typecheck *lean_code* and return (returncode, stdout, stderr)."""
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
        """Kill any running process. Called when the pipeline finishes."""
        if self._proc is not None and self._proc.returncode is None:
            self._proc.kill()
            await self._proc.wait()
            unregister_process(self._proc)
        self._proc = None
