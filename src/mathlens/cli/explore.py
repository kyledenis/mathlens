"""mathlens explore — quick verified exploration command."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer

from mathlens.cli.app import app
from mathlens.cli.common import apply_flag_overrides, build_pipeline
from mathlens.config.settings import MathLensSettings
from mathlens.models import Badge, OutputFormat, PipelineMode, PipelineStage
from mathlens.pipeline.orchestrator import ExplorationResult
from mathlens.ui.console import console, format_badge, format_duration, format_topic_header
from mathlens.ui.errors import format_error, format_refuted_error
from mathlens.ui.progress import PipelineProgress

_CONFIG_PATH = Path.home() / ".config" / "mathlens" / "config.toml"
_progress = PipelineProgress()

_STAGE_ORDER = [
    PipelineStage.planning,
    PipelineStage.verification,
    PipelineStage.visualization,
    PipelineStage.summarization,
]


def run_explore(
    query: str,
    settings: MathLensSettings,
    format_override: Optional[str] = None,
    no_verify: bool = False,
    mode: PipelineMode = PipelineMode.explore,
    quiet: bool = False,
) -> ExplorationResult:
    """Build pipeline and run, showing a live spinner for each stage."""
    orchestrator = build_pipeline(settings)
    output_format: Optional[OutputFormat] = None
    if format_override is not None:
        output_format = OutputFormat(format_override)

    if quiet:
        return asyncio.run(
            orchestrator.run(
                query=query,
                mode=mode,
                output_format=output_format,
                skip_verification=no_verify,
            )
        )

    # Run with live progress spinner
    stage_starts: dict[PipelineStage, float] = {}
    result_holder: list[ExplorationResult] = []
    exception_holder: list[Exception] = []

    import time

    def on_stage(stage: PipelineStage, event: str) -> None:
        if event == "start":
            stage_starts[stage] = time.monotonic()
            status.update(f"  {_progress.format_stage_start(stage)}")
        elif event == "done":
            elapsed = time.monotonic() - stage_starts.get(stage, time.monotonic())
            console.print(_progress.format_stage_done(stage, elapsed))

    async def _run() -> ExplorationResult:
        return await orchestrator.run(
            query=query,
            mode=mode,
            output_format=output_format,
            skip_verification=no_verify,
            on_stage=on_stage,
        )

    console.print()
    with console.status("  Initializing...", spinner="dots") as status:
        try:
            result = asyncio.run(_run())
        except Exception as exc:
            raise

    return result


def display_result(result: ExplorationResult) -> None:
    """Render an ExplorationResult to the terminal using Rich."""
    # 1. Topic header
    console.print(format_topic_header(result.plan.topic))

    # 2. Verification badge
    badge = Badge.from_status(result.verification.status)
    console.print(format_badge(badge))

    # 3. If refuted: show error and return early
    if result.verification.should_halt:
        reason = result.verification.failure_reason or "Unknown reason"
        console.print(format_refuted_error(reason, result.verification.lean_output))
        return

    # 4. Visualization output path
    if result.visualization is not None:
        console.print(f"[cyan]Output:[/cyan] {result.visualization.output_path}")

    # 5. Key insights from summary
    if result.summary is not None:
        for insight in result.summary.key_insights:
            console.print(f"  • {insight}")

    # 6. Duration
    console.print(f"[dim]Completed in {format_duration(result.duration_seconds)}[/dim]")


@app.command()
def explore(
    query: str = typer.Argument(..., help="Math topic or question to explore."),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="LLM provider: api, cli, or local."),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model name override."),
    local: bool = typer.Option(False, "--local", help="Shorthand for --provider local."),
    format: Optional[str] = typer.Option(None, "--format", "-f", help="Output format: video, frames, or diagram."),
    quality: Optional[str] = typer.Option(None, "--quality", "-q", help="Render quality: low, medium, high, production."),
    no_verify: bool = typer.Option(False, "--no-verify", help="Skip formal verification step."),
    verify_timeout: Optional[int] = typer.Option(None, "--verify-timeout", help="Verification timeout in seconds."),
    retry: bool = typer.Option(False, "--retry", help="Retry a previously failed exploration."),
    force: bool = typer.Option(False, "--force", help="Force re-run even if already completed."),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress non-essential output."),
    no_open: bool = typer.Option(False, "--no-open", help="Do not open the output file when done."),
    json_output: bool = typer.Option(False, "--json", help="Output result as JSON."),
) -> None:
    """Explore a math topic: plan → verify → visualize → summarize."""
    try:
        settings = MathLensSettings.from_toml(_CONFIG_PATH)
        apply_flag_overrides(
            settings,
            provider=provider,
            model=model,
            local=local,
            format=format,
            quality=quality,
            verify_timeout=verify_timeout,
            no_verify=no_verify,
            no_open=no_open,
            quiet=quiet,
        )
        result = run_explore(query, settings, format_override=format, no_verify=no_verify, quiet=quiet)
        display_result(result)
    except Exception as exc:
        console.print(format_error(str(exc)))
        raise typer.Exit(code=1)
