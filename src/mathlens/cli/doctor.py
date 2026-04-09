"""mathlens doctor — dependency health checks with cross-platform install support."""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from typing import NamedTuple

import typer
from rich import box
from rich.table import Table

from mathlens.cli.app import app
from mathlens.ui.console import console


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
    return _Check("Lean 4", path is not None, path or "not found")


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

_INSTALL_HINTS: dict[str, dict[str, str]] = {
    "Lean 4": {
        "macos": "curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh | sh",
        "linux": "curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh | sh",
        "windows": "winget install leanprover.elan",
    },
    "ffmpeg": {
        "macos": "brew install ffmpeg",
        "linux": "sudo apt install ffmpeg",
        "windows": "winget install ffmpeg",
    },
    "LaTeX": {
        "macos": "brew install --cask basictex",
        "linux": "sudo apt install texlive-base",
        "windows": "winget install MiKTeX.MiKTeX",
    },
    "claude (CLI)": {
        "macos": "npm install -g @anthropic-ai/claude-code",
        "linux": "npm install -g @anthropic-ai/claude-code",
        "windows": "npm install -g @anthropic-ai/claude-code",
    },
    "ollama": {
        "macos": "brew install ollama",
        "linux": "curl -fsSL https://ollama.com/install.sh | sh",
        "windows": "winget install Ollama.Ollama",
    },
    "Manim CE": {
        "macos": "pip install manim",
        "linux": "pip install manim",
        "windows": "pip install manim",
    },
}


def _install_hint(component: str) -> str | None:
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
    checks = [
        _check_python(),
        _check_lean(),
        _check_manim(),
        _check_ffmpeg(),
        _check_latex(),
        _check_claude(),
        _check_ollama(),
    ]

    table = Table(
        title=f"MathLens Dependency Health ({plat})",
        show_header=True,
        header_style="bold",
        box=box.ROUNDED,
        border_style="dim",
    )
    table.add_column("Component", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Details")

    for check in checks:
        status = "[green]\u2713[/green]" if check.ok else "[red]\u2717[/red]"
        table.add_row(check.component, status, check.details)

    console.print(table)

    all_ok = all(c.ok for c in checks)
    failed = [c for c in checks if not c.ok]

    if all_ok:
        console.print()
        console.print("  [green]All checks passed.[/green] Ready to go.")
        console.print()
        console.print('  [dim]Try:[/dim] mathlens explore "why does e^(i*pi) = -1"')
    else:
        console.print()
        console.print("  [bold]Next steps:[/bold]")
        for c in failed:
            hint = _install_hint(c.component)
            if hint:
                console.print(f"    {c.component}: [dim]{hint}[/dim]")
            else:
                console.print(f"    {c.component}: [dim]no installer available for {plat}[/dim]")
        console.print()
        console.print("  [dim]MathLens works without optional deps — missing tools only affect specific features.[/dim]")
        if not install:
            console.print("  [dim]Run [bold]mathlens doctor --install[/bold] to attempt automatic installation.[/dim]")

    # --install: attempt to install missing deps
    if install and failed:
        console.print()
        console.print("[bold]Installing missing dependencies...[/bold]")
        for c in failed:
            hint = _install_hint(c.component)
            if not hint:
                console.print(f"  [yellow]-[/yellow] {c.component}: no automatic installer for {plat}")
                continue
            console.print(f"  [dim]>[/dim] Installing {c.component}...")
            try:
                result = subprocess.run(
                    hint, shell=True, capture_output=True, text=True, timeout=300,
                )
                if result.returncode == 0:
                    console.print(f"  [green]>[/green] {c.component} installed")
                else:
                    stderr_excerpt = result.stderr.strip()[:200]
                    console.print(f"  [red]>[/red] {c.component} failed: {stderr_excerpt}")
                    console.print(f"      [dim]Manual install:[/dim] {hint}")
            except subprocess.TimeoutExpired:
                console.print(f"  [red]>[/red] {c.component} timed out")
                console.print(f"      [dim]Manual install:[/dim] {hint}")
            except Exception as e:
                console.print(f"  [red]>[/red] {c.component} error: {e}")
                console.print(f"      [dim]Manual install:[/dim] {hint}")

    # --fix: repair workspace
    if fix:
        from pathlib import Path as _Path

        from mathlens.config.settings import MathLensSettings
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
