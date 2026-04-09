"""mathlens prove / viz / vis / summarize — toolkit commands."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer

from mathlens.cli.app import app
from mathlens.cli.common import apply_flag_overrides, build_pipeline
from mathlens.config.settings import MathLensSettings
from mathlens.models import Badge, OutputFormat, PipelineMode, VerificationResult
from mathlens.pipeline.orchestrator import ExplorationResult
from mathlens.ui.console import console, format_badge, format_duration
from mathlens.ui.errors import format_error

_CONFIG_PATH = Path.home() / ".config" / "mathlens" / "config.toml"


# ---------------------------------------------------------------------------
# Helpers (extracted for easy patching in tests)
# ---------------------------------------------------------------------------


def run_prove(
    statement: str,
    settings: MathLensSettings,
) -> VerificationResult:
    """Build pipeline and run verification on a single statement."""
    orchestrator = build_pipeline(settings)
    return asyncio.run(
        orchestrator._verifier.verify([statement], PipelineMode.explore)
    )


def run_viz(
    description: str,
    settings: MathLensSettings,
) -> ExplorationResult:
    """Build pipeline and run full explore with skip_verification=True."""
    orchestrator = build_pipeline(settings)
    return asyncio.run(
        orchestrator.run(
            query=description,
            mode=PipelineMode.explore,
            skip_verification=True,
        )
    )


# ---------------------------------------------------------------------------
# prove
# ---------------------------------------------------------------------------


@app.command()
def prove(
    statement: str = typer.Argument(..., help="Mathematical statement to verify."),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="LLM provider: api, cli, or local."),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model name override."),
    local: bool = typer.Option(False, "--local", help="Shorthand for --provider local."),
) -> None:
    """Prove a mathematical statement using Lean 4 verification."""
    try:
        settings = MathLensSettings.from_toml(_CONFIG_PATH)
        apply_flag_overrides(settings, provider=provider, model=model, local=local)
        result = run_prove(statement, settings)
        badge = Badge.from_status(result.status)
        console.print(format_badge(badge))
        console.print(f"[dim]Verified in {format_duration(result.duration_seconds)}[/dim]")
        if result.failure_reason:
            console.print(f"[yellow]Reason:[/yellow] {result.failure_reason}")
    except Exception as exc:
        console.print(format_error(str(exc)))
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# viz
# ---------------------------------------------------------------------------


def _run_viz_command(
    description: str,
    provider: Optional[str],
    format: Optional[str],
    local: bool,
) -> None:
    """Shared implementation for viz/vis."""
    try:
        settings = MathLensSettings.from_toml(_CONFIG_PATH)
        apply_flag_overrides(settings, provider=provider, local=local, format=format)
        result = run_viz(description, settings)
        if result.visualization is not None:
            console.print(f"[cyan]Output:[/cyan] {result.visualization.output_path}")
    except Exception as exc:
        console.print(format_error(str(exc)))
        raise typer.Exit(code=1)


@app.command()
def vis(
    description: str = typer.Argument(..., help="Math description to visualize."),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="LLM provider: api, cli, or local."),
    format: Optional[str] = typer.Option(None, "--format", "-f", help="Output format: video, frames, or diagram."),
    local: bool = typer.Option(False, "--local", help="Shorthand for --provider local."),
) -> None:
    """Visualize a math concept (also available as 'viz')."""
    _run_viz_command(description, provider, format, local)


@app.command(name="viz", hidden=True)
def viz(
    description: str = typer.Argument(..., help="Math description to visualize."),
    provider: Optional[str] = typer.Option(None, "--provider", "-p"),
    format: Optional[str] = typer.Option(None, "--format", "-f"),
    local: bool = typer.Option(False, "--local"),
) -> None:
    """Alias for vis."""
    _run_viz_command(description, provider, format, local)


# ---------------------------------------------------------------------------
# summarize
# ---------------------------------------------------------------------------


@app.command()
def summarize(
    workspace_path: str = typer.Argument(..., help="Path to an existing workspace to summarize."),
) -> None:
    """Summarize an existing exploration workspace."""
    console.print("[dim]Summarize command coming in Phase 3.[/dim]")
