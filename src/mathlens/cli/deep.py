"""mathlens deep — production quality pipeline."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer

from mathlens.cli.app import app
from mathlens.cli.common import apply_flag_overrides, build_pipeline
from mathlens.cli.explore import display_result
from mathlens.config.settings import MathLensSettings
from mathlens.models import OutputFormat, PipelineMode
from mathlens.pipeline.orchestrator import ExplorationResult
from mathlens.ui.console import console
from mathlens.ui.errors import format_error

_CONFIG_PATH = Path.home() / ".config" / "mathlens" / "config.toml"


def run_deep(
    query: str,
    settings: MathLensSettings,
    format_override: Optional[str] = None,
    no_verify: bool = False,
) -> ExplorationResult:
    """Build pipeline and run the deep mode, returning an ExplorationResult."""
    orchestrator = build_pipeline(settings)
    output_format: Optional[OutputFormat] = None
    if format_override is not None:
        output_format = OutputFormat(format_override)
    return asyncio.run(
        orchestrator.run(
            query=query,
            mode=PipelineMode.deep,
            output_format=output_format,
            skip_verification=no_verify,
        )
    )


@app.command()
def deep(
    query: str = typer.Argument(..., help="Math topic or question to explore in depth."),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="LLM provider: api, cli, or local."),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model name override."),
    local: bool = typer.Option(False, "--local", help="Shorthand for --provider local."),
    format: Optional[str] = typer.Option(None, "--format", "-f", help="Output format: video, frames, or diagram."),
    no_verify: bool = typer.Option(False, "--no-verify", help="Skip formal verification step."),
    verify_timeout: Optional[int] = typer.Option(None, "--verify-timeout", help="Verification timeout in seconds."),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress non-essential output."),
    no_open: bool = typer.Option(False, "--no-open", help="Do not open the output file when done."),
) -> None:
    """Deep-dive a math topic at production quality: plan → verify → visualize → summarize."""
    try:
        settings = MathLensSettings.from_toml(_CONFIG_PATH)
        apply_flag_overrides(
            settings,
            provider=provider,
            model=model,
            local=local,
            format=format,
            quality="production",
            verify_timeout=verify_timeout,
            no_verify=no_verify,
            no_open=no_open,
            quiet=quiet,
        )
        result = run_deep(query, settings, format_override=format, no_verify=no_verify)
        display_result(result)
    except Exception as exc:
        console.print(format_error(str(exc)))
        raise typer.Exit(code=1)
