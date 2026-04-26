"""mathlens deep — production quality pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from mathlens.cli.app import app
from mathlens.cli.common import apply_flag_overrides
from mathlens.cli.explore import display_result, run_explore
from mathlens.config.settings import MathLensSettings
from mathlens.lifecycle import cleanup, install_signal_handlers
from mathlens.models import PipelineMode
from mathlens.ui.console import console
from mathlens.ui.errors import format_error

_CONFIG_PATH = Path.home() / ".config" / "mathlens" / "config.toml"


# run_deep is kept as an alias for patching in tests
def run_deep(
    query: str,
    settings: MathLensSettings,
    format_override: Optional[str] = None,
    no_verify: bool = False,
    quiet: bool = False,
):
    return run_explore(
        query, settings, format_override=format_override,
        no_verify=no_verify, mode=PipelineMode.deep, quiet=quiet,
    )


@app.command(rich_help_panel="Explore")
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
    install_signal_handlers()
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
        result = run_deep(query, settings, format_override=format, no_verify=no_verify, quiet=quiet)
        display_result(result)
    except KeyboardInterrupt:
        cleanup()
        console.print("\n  [dim]Interrupted. All background processes stopped.[/dim]")
        raise typer.Exit(code=130)
    except Exception as exc:
        cleanup()
        console.print(format_error(str(exc)))
        raise typer.Exit(code=1)
