"""mathlens doctor — dependency health checks."""
from __future__ import annotations

import shutil
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


def _check_python() -> _Check:
    vi = sys.version_info
    ok = (vi.major, vi.minor) >= (3, 11)
    details = f"{vi.major}.{vi.minor}.{vi.micro}"
    return _Check("Python", ok, details)


def _check_lean() -> _Check:
    path = shutil.which("lean")
    ok = path is not None
    return _Check("Lean 4", ok, path or "not found")


def _check_manim() -> _Check:
    try:
        import manim  # type: ignore
        version = getattr(manim, "__version__", "unknown")
        return _Check("Manim CE", True, version)
    except ImportError:
        return _Check("Manim CE", False, "not found")


def _check_ffmpeg() -> _Check:
    path = shutil.which("ffmpeg")
    ok = path is not None
    return _Check("ffmpeg", ok, path or "not found")


def _check_latex() -> _Check:
    for binary in ("pdflatex", "xelatex", "lualatex"):
        path = shutil.which(binary)
        if path:
            return _Check("LaTeX", True, path)
    return _Check("LaTeX", False, "not found")


def _check_claude() -> _Check:
    path = shutil.which("claude")
    ok = path is not None
    return _Check("claude (CLI)", ok, path or "not found")


def _check_ollama() -> _Check:
    path = shutil.which("ollama")
    ok = path is not None
    return _Check("ollama", ok, path or "not found")


INSTALL_HINTS: dict[str, str] = {
    "Lean 4": "curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh | sh",
    "ffmpeg": "brew install ffmpeg",
    "LaTeX": "brew install --cask basictex",
    "claude (CLI)": "npm install -g @anthropic-ai/claude-code",
    "ollama": "brew install ollama",
    "Manim CE": "pip install manim",
}


def _install_hint(component: str) -> str | None:
    return INSTALL_HINTS.get(component)


@app.command()
def doctor(
    fix: bool = typer.Option(False, "--fix", help="Repair workspace issues (stale locks, tmp files)."),
    install: bool = typer.Option(False, "--install", help="Attempt to install missing dependencies."),
) -> None:
    """Check dependencies and workspace health."""
    checks = [
        _check_python(),
        _check_lean(),
        _check_manim(),
        _check_ffmpeg(),
        _check_latex(),
        _check_claude(),
        _check_ollama(),
    ]

    table = Table(title="MathLens Dependency Health", show_header=True, header_style="bold", box=box.ROUNDED)
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
        console.print("  [dim]Try:[/dim] mathlens explore \"why does e^(i*pi) = -1\"")
    else:
        console.print()
        console.print("  [bold]Next steps:[/bold]")
        for c in failed:
            hint = _install_hint(c.component)
            if hint:
                console.print(f"    {c.component}: {hint}")
        console.print()
        console.print("  [dim]MathLens works without optional deps — missing tools only affect specific features.[/dim]")
        if not install:
            console.print("  [dim]Run [bold]mathlens doctor --install[/bold] to attempt automatic installation.[/dim]")

    if install and failed:
        import subprocess

        console.print()
        console.print("[bold]Installing missing dependencies...[/bold]")
        for c in failed:
            hint = _install_hint(c.component)
            if not hint:
                console.print(f"  [yellow]-[/yellow] {c.component}: no automatic installer available")
                continue
            console.print(f"  [dim]>[/dim] Installing {c.component}...")
            try:
                result = subprocess.run(hint, shell=True, capture_output=True, text=True, timeout=300)
                if result.returncode == 0:
                    console.print(f"  [green]>[/green] {c.component} installed")
                else:
                    console.print(f"  [red]>[/red] {c.component} failed: {result.stderr.strip()[:200]}")
                    console.print(f"      [dim]Manual install:[/dim] {hint}")
            except subprocess.TimeoutExpired:
                console.print(f"  [red]>[/red] {c.component} timed out")
                console.print(f"      [dim]Manual install:[/dim] {hint}")
            except Exception as e:
                console.print(f"  [red]>[/red] {c.component} error: {e}")
                console.print(f"      [dim]Manual install:[/dim] {hint}")

    if fix:
        from pathlib import Path as _Path
        from mathlens.workspace.repair import WorkspaceRepair
        from mathlens.config.settings import MathLensSettings

        config_path = _Path.home() / ".config" / "mathlens" / "config.toml"
        settings = MathLensSettings.from_toml(config_path)
        repair_tool = WorkspaceRepair(_Path(settings.workspace.path).expanduser())
        actions = repair_tool.fix()
        if actions:
            console.print()
            console.print("[bold]Repairs:[/bold]")
            for action in actions:
                console.print(f"  [green]✓[/green] {action}")
        else:
            console.print()
            console.print("  [dim]No workspace issues to fix[/dim]")
