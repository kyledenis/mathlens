"""mathlens doctor — dependency health checks with cross-platform install support."""

from __future__ import annotations

import platform
import random
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path as _Path
from typing import NamedTuple

import typer
from rich import box

from mathlens.cli.app import app
from mathlens.config.settings import MathLensSettings
from mathlens.ui.console import console, make_table

_SUGGESTIONS = [
    # Calculus & Analysis
    "why does the harmonic series diverge",
    "prove the fundamental theorem of calculus",
    "why does the sum of 1/n^2 converge to pi^2/6",
    "visualize the epsilon-delta definition of a limit",
    "how does Taylor series approximate sin(x)",
    # Linear Algebra
    "what do eigenvalues geometrically represent",
    "why is the determinant the volume scaling factor",
    "visualize singular value decomposition",
    "how does a matrix transform the unit circle",
    "prove that orthogonal matrices preserve distances",
    # Number Theory & Discrete
    "why are there infinitely many primes",
    "visualize the Sieve of Eratosthenes",
    "prove there is no largest prime number",
    "what makes Euler's totient function multiplicative",
    # Abstract Algebra & Topology
    "why is the square root of 2 irrational",
    "visualize group actions on a polygon",
    "what does a Mobius strip look like in 3D",
    "why can't you comb a hairy ball flat",
    # Probability & Applied
    "visualize the central limit theorem",
    "why does e appear in compound interest",
    "prove the Cauchy-Schwarz inequality",
    "how does gradient descent find minima",
    # Gems
    "why does e^(i*pi) + 1 = 0",
    "prove the Pythagorean theorem visually",
    "what is the Banach-Tarski paradox",
    "visualize Fourier series building a square wave",
    "why is 0.999... exactly equal to 1",
]


def _random_suggestion() -> str:
    return random.choice(_SUGGESTIONS)


class _Check(NamedTuple):
    component: str
    ok: bool
    details: str


def _platform() -> str:
    """Return 'macos', 'linux', or 'windows'."""
    s = platform.system().lower()
    if s == "darwin":
        return "macos"
    if s == "windows":
        return "windows"
    return "linux"


# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------

def _check_python() -> _Check:
    vi = sys.version_info
    ok = (vi.major, vi.minor) >= (3, 11)
    details = f"{vi.major}.{vi.minor}.{vi.micro}"
    return _Check("Python", ok, details)


def _check_lean() -> _Check:
    path = shutil.which("lean")
    if not path:
        return _Check("Lean 4", False, "not found")
    lake_path = shutil.which("lake")
    if not lake_path:
        return _Check("Lean 4", False, f"{path} (lake not found — install elan)")
    return _Check("Lean 4", True, path)


def _check_mathlib() -> _Check:
    settings = MathLensSettings.from_toml(_Path.home() / ".config" / "mathlens" / "config.toml")
    workspace = _Path(settings.workspace.path).expanduser()
    project_dir = workspace / "lean-project"
    lakefile = project_dir / "lakefile.lean"
    lake_dir = project_dir / ".lake"
    if lakefile.exists() and lake_dir.exists():
        return _Check("Mathlib", True, str(project_dir))
    if lakefile.exists():
        return _Check("Mathlib", False, "project exists but not built")
    return _Check("Mathlib", False, "not set up")


def _check_manim() -> _Check:
    try:
        import manim  # type: ignore[import-untyped]
        version = getattr(manim, "__version__", "unknown")
        return _Check("Manim CE", True, version)
    except ImportError:
        return _Check("Manim CE", False, "not found")


def _check_ffmpeg() -> _Check:
    path = shutil.which("ffmpeg")
    return _Check("ffmpeg", path is not None, path or "not found")


def _check_latex() -> _Check:
    for binary in ("pdflatex", "xelatex", "lualatex"):
        path = shutil.which(binary)
        if path:
            # Check that Manim's required package (standalone.cls) is present
            try:
                result = subprocess.run(
                    ["kpsewhich", "standalone.cls"],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode != 0 or not result.stdout.strip():
                    return _Check("LaTeX", False, f"{path} (missing standalone.cls)")
            except Exception:
                pass  # kpsewhich not available — assume OK
            return _Check("LaTeX", True, path)
    return _Check("LaTeX", False, "not found")


def _check_claude() -> _Check:
    path = shutil.which("claude")
    return _Check("claude (CLI)", path is not None, path or "not found")


def _check_ollama() -> _Check:
    path = shutil.which("ollama")
    return _Check("ollama", path is not None, path or "not found")


# ---------------------------------------------------------------------------
# Cross-platform install hints
# ---------------------------------------------------------------------------

@dataclass
class _InstallCmd:
    """An install command — either safe arg list or shell string (for pipes)."""
    args: list[str]
    shell: bool = False
    display: str = ""

    def __post_init__(self) -> None:
        if not self.display:
            self.display = " ".join(self.args)


def _cmd(args: list[str]) -> _InstallCmd:
    return _InstallCmd(args=args)


def _shell_cmd(cmd: str) -> _InstallCmd:
    """For commands requiring shell features (pipes). Display string = the raw command."""
    return _InstallCmd(args=[cmd], shell=True, display=cmd)


_INSTALL_HINTS: dict[str, dict[str, _InstallCmd]] = {
    "Lean 4": {
        "macos": _shell_cmd("curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh | sh"),
        "linux": _shell_cmd("curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh | sh"),
        "windows": _cmd(["winget", "install", "leanprover.elan"]),
    },
    "ffmpeg": {
        "macos": _cmd(["brew", "install", "ffmpeg"]),
        "linux": _cmd(["sudo", "apt", "install", "-y", "ffmpeg"]),
        "windows": _cmd(["winget", "install", "ffmpeg"]),
    },
    "LaTeX": {
        "macos": _shell_cmd(
            "brew install --cask basictex && "
            "sudo tlmgr update --self && "
            "sudo tlmgr install standalone preview dvisvgm doublestroke "
            "setspace rsfs jknapltx wasy wasysym sttools mathtools"
        ),
        "linux": _cmd(["sudo", "apt", "install", "-y", "texlive", "texlive-latex-extra"]),
        "windows": _cmd(["winget", "install", "MiKTeX.MiKTeX"]),
    },
    "claude (CLI)": {
        "macos": _cmd(["npm", "install", "-g", "@anthropic-ai/claude-code"]),
        "linux": _cmd(["npm", "install", "-g", "@anthropic-ai/claude-code"]),
        "windows": _cmd(["npm", "install", "-g", "@anthropic-ai/claude-code"]),
    },
    "ollama": {
        "macos": _cmd(["brew", "install", "ollama"]),
        "linux": _shell_cmd("curl -fsSL https://ollama.com/install.sh | sh"),
        "windows": _cmd(["winget", "install", "Ollama.Ollama"]),
    },
    "Manim CE": {
        "macos": _cmd(["pip", "install", "manim"]),
        "linux": _cmd(["pip", "install", "manim"]),
        "windows": _cmd(["pip", "install", "manim"]),
    },
}


def _install_hint(component: str) -> _InstallCmd | None:
    """Return the install command for this platform, or None."""
    hints = _INSTALL_HINTS.get(component)
    if hints is None:
        return None
    return hints.get(_platform())


# ---------------------------------------------------------------------------
# Doctor command
# ---------------------------------------------------------------------------

@app.command()
def doctor(
    fix: bool = typer.Option(False, "--fix", help="Repair workspace issues (stale locks, tmp files)."),
    install: bool = typer.Option(False, "--install", help="Attempt to install missing dependencies."),
) -> None:
    """Check dependencies and workspace health."""
    plat = _platform()
    required = [_check_python(), _check_manim(), _check_ffmpeg()]
    optional = [_check_lean(), _check_mathlib(), _check_latex(), _check_claude(), _check_ollama()]

    checks = required + optional

    table, panel = make_table(
        f"Dependencies ({plat})",
        [("Component", "bold"), ("Status", None), ("Details", "dim")],
    )

    table.add_row("[bold]Required[/bold]", "", "")
    for check in required:
        status = "[green]\u2713[/green]" if check.ok else "[red]\u2717[/red]"
        table.add_row(f"  {check.component}", status, check.details)

    table.add_row("", "", "")
    table.add_row("[bold]Optional[/bold]", "", "")
    for check in optional:
        status = "[green]\u2713[/green]" if check.ok else "[yellow]\u2717[/yellow]"
        table.add_row(f"  {check.component}", status, check.details)

    console.print(panel)

    all_ok = all(c.ok for c in checks)
    failed = [c for c in checks if not c.ok]

    if all_ok:
        console.print()
        console.print("  [green]All checks passed.[/green] Ready to go.")
        console.print()
        console.print(f"  [dim]Try:[/dim] mathlens explore \"{_random_suggestion()}\"")
    else:
        console.print()
        console.print("  [bold]Next steps:[/bold]")
        for c in failed:
            cmd = _install_hint(c.component)
            if cmd:
                console.print(f"    {c.component}: [dim]{cmd.display}[/dim]")
            else:
                console.print(f"    {c.component}: [dim]no installer available for {plat}[/dim]")
        console.print()
        console.print("  [dim]MathLens works without optional deps — missing tools only affect specific features.[/dim]")
        if not install:
            console.print("  [dim]Run [bold]mathlens doctor --install[/bold] to attempt automatic installation.[/dim]")

    # --install: attempt to install missing deps
    if install and failed:
        import asyncio as _asyncio

        console.print()
        console.print("[bold]Installing missing dependencies...[/bold]")
        for c in failed:
            # Mathlib has special async setup via Lake
            if c.component == "Mathlib":
                console.print(f"  [dim]>[/dim] Setting up Mathlib (this downloads ~2 GB, may take a few minutes)...")
                try:
                    from mathlens.workspace.lean_project import LeanProject
                    settings = MathLensSettings.from_toml(_Path.home() / ".config" / "mathlens" / "config.toml")
                    workspace = _Path(settings.workspace.path).expanduser()
                    project = LeanProject(workspace / "lean-project")
                    success, msg = _asyncio.run(project.setup(timeout=600))
                    if success:
                        console.print(f"  [green]>[/green] Mathlib ready")
                    else:
                        console.print(f"  [red]>[/red] Mathlib setup failed: {msg}")
                except Exception as e:
                    console.print(f"  [red]>[/red] Mathlib error: {e}")
                continue

            cmd = _install_hint(c.component)
            if not cmd:
                console.print(f"  [yellow]-[/yellow] {c.component}: no automatic installer for {plat}")
                continue
            console.print(f"  [dim]>[/dim] Installing {c.component}...")
            try:
                if cmd.shell:
                    run_result = subprocess.run(
                        cmd.args[0], shell=True, capture_output=True, text=True, timeout=300,
                    )
                else:
                    run_result = subprocess.run(
                        cmd.args, capture_output=True, text=True, timeout=300,
                    )
                if run_result.returncode == 0:
                    console.print(f"  [green]>[/green] {c.component} installed")
                else:
                    stderr_excerpt = run_result.stderr.strip()[:200]
                    console.print(f"  [red]>[/red] {c.component} failed: {stderr_excerpt}")
                    console.print(f"      [dim]Manual install:[/dim] {cmd.display}")
            except subprocess.TimeoutExpired:
                console.print(f"  [red]>[/red] {c.component} timed out")
                console.print(f"      [dim]Manual install:[/dim] {cmd.display}")
            except Exception as e:
                console.print(f"  [red]>[/red] {c.component} error: {e}")
                console.print(f"      [dim]Manual install:[/dim] {cmd.display}")

    # --fix: repair workspace
    if fix:
        from mathlens.workspace.repair import WorkspaceRepair

        config_path = _Path.home() / ".config" / "mathlens" / "config.toml"
        settings = MathLensSettings.from_toml(config_path)
        repair_tool = WorkspaceRepair(_Path(settings.workspace.path).expanduser())
        actions = repair_tool.fix()
        if actions:
            console.print()
            console.print("[bold]Repairs:[/bold]")
            for action in actions:
                console.print(f"  [green]>[/green] {action}")
        else:
            console.print()
            console.print("  [dim]No workspace issues to fix[/dim]")
