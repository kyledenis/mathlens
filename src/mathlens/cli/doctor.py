"""mathlens doctor — dependency health checks."""
from __future__ import annotations

import shutil
import sys
from typing import NamedTuple

import typer
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


@app.command()
def doctor(
    fix: bool = typer.Option(False, "--fix", help="Attempt to fix missing dependencies (not yet implemented)."),
) -> None:
    """Check that required and optional dependencies are available."""
    checks = [
        _check_python(),
        _check_lean(),
        _check_manim(),
        _check_ffmpeg(),
        _check_latex(),
        _check_claude(),
        _check_ollama(),
    ]

    table = Table(title="MathLens Dependency Health", show_header=True, header_style="bold")
    table.add_column("Component", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Details")

    for check in checks:
        status = "[green]\u2713[/green]" if check.ok else "[red]\u2717[/red]"
        table.add_row(check.component, status, check.details)

    console.print(table)

    all_ok = all(c.ok for c in checks)
    if all_ok:
        console.print("[green]All checks passed.[/green]")
    else:
        console.print("[yellow]Some dependencies are missing.[/yellow]")
        console.print(
            "MathLens degrades gracefully — missing optional tools only affect specific features."
        )
