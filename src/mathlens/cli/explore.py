"""mathlens explore — quick verified exploration command."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer

from mathlens.cli.app import app
from mathlens.cli.common import apply_flag_overrides, build_pipeline
from mathlens.config.settings import MathLensSettings
from mathlens.lifecycle import cleanup, install_signal_handlers
from mathlens.models import Badge, OutputFormat, PipelineMode, PipelineStage, VerificationStatus
from mathlens.pipeline.orchestrator import ExplorationResult, TokenUsage
from mathlens.ui.console import console, format_badge, format_duration, format_topic_header
from mathlens.ui.errors import format_error, format_refuted_error
from mathlens.ui.progress import DurationTracker, PipelineProgress

_CONFIG_PATH = Path.home() / ".config" / "mathlens" / "config.toml"


def run_explore(
    query: str,
    settings: MathLensSettings,
    format_override: Optional[str] = None,
    no_verify: bool = False,
    mode: PipelineMode = PipelineMode.explore,
    quiet: bool = False,
    force: bool = False,
) -> ExplorationResult:
    """Build pipeline and run, showing a live spinner for each stage."""
    orchestrator = build_pipeline(settings)
    provider_name = settings.provider.default
    workspace_root = Path(settings.workspace.path).expanduser()
    tracker = DurationTracker(workspace_root / "duration_history.json")
    progress = PipelineProgress(mode, tracker=tracker, provider=provider_name)
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
                force=force,
            )
        )

    # Run with live progress spinner
    stage_starts: dict[PipelineStage, float] = {}

    import time

    def on_stage(stage: PipelineStage, event: str) -> None:
        if event == "start":
            stage_starts[stage] = time.monotonic()
            status.update(f"  {progress.format_stage_start(stage)}")
        elif event == "done":
            elapsed = time.monotonic() - stage_starts.get(stage, time.monotonic())
            console.print(progress.format_stage_done(stage, elapsed))
            tracker.record(stage, mode, elapsed, provider=provider_name)

    async def _run() -> ExplorationResult:
        return await orchestrator.run(
            query=query,
            mode=mode,
            output_format=output_format,
            skip_verification=no_verify,
            force=force,
            on_stage=on_stage,
        )

    console.print()
    console.print(f"  {progress.format_total_estimate()}")
    with console.status("  Initializing...", spinner="dots") as status:
        try:
            result = asyncio.run(_run())
        except Exception as exc:
            raise

    return result


def display_result(result: ExplorationResult) -> None:
    """Render an ExplorationResult to the terminal using Rich."""
    console.print()

    # 1. Topic header
    console.print(format_topic_header(result.plan.topic))
    console.print()

    # 2. Verification badge — only show if verification actually ran
    if result.verification.status != VerificationStatus.skipped:
        badge = Badge.from_status(result.verification.status)
        console.print(f"  {format_badge(badge)}")

        # If refuted: show error and return early
        if result.verification.should_halt:
            reason = result.verification.failure_reason or "Unknown reason"
            console.print(format_refuted_error(reason, result.verification.lean_output))
            return
        console.print()

    # 3. Key insights from summary
    if result.summary is not None:
        for insight in result.summary.key_insights:
            console.print(f"  [dim]•[/dim] {insight}")
        console.print()

    # 4. Visualization output
    video_path = _find_rendered_video(result)
    if video_path:
        console.print(f"  [dim]Video:[/dim] {video_path}")
    elif result.visualization is not None:
        console.print(f"  [yellow]Render failed:[/yellow] no video produced")

    # 5. Footer — duration, tokens, mode
    if result.duration_seconds == 0.0:
        parts = ["cached"]
    else:
        parts = [format_duration(result.duration_seconds)]
    parts.append(result.meta.mode.value)
    if result.usage.has_data:
        parts.append(f"{result.usage.total:,} tokens")
    console.print(f"  [dim]{' · '.join(parts)}[/dim]")


def _find_rendered_video(result: ExplorationResult) -> Path | None:
    """Find the final rendered video, excluding Manim's partial movie files."""
    if result.visualization is None:
        return None
    output_dir = result.visualization.output_path
    if not output_dir.is_dir():
        return None
    # Manim writes final videos to videos/{scene}/{quality}/{ClassName}.mp4
    # Partial files are in videos/{scene}/{quality}/partial_movie_files/
    for ext in ("*.mp4", "*.gif", "*.png"):
        for f in output_dir.glob(f"**/{ext}"):
            if "partial_movie_files" not in str(f):
                return f
    return None


def _auto_open_output(result: ExplorationResult) -> None:
    """Open the rendered video, if any."""
    import platform
    import subprocess as _sp

    video = _find_rendered_video(result)
    if video is None:
        return
    target = str(video)
    system = platform.system()
    if system == "Darwin":
        _sp.run(["open", target], check=False)
    elif system == "Linux":
        _sp.run(["xdg-open", target], check=False)
    elif system == "Windows":
        _sp.run(["start", target], check=False, shell=True)


@app.command(rich_help_panel="Explore")
def explore(
    query: str = typer.Argument(..., help="Math topic or question to explore."),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="LLM provider: api, cli, or local."),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model name override."),
    local: bool = typer.Option(False, "--local", help="Shorthand for --provider local."),
    format: Optional[str] = typer.Option(None, "--format", "-f", help="Output format: video, frames, or diagram."),
    quality: Optional[str] = typer.Option(None, "--quality", "-q", help="Render quality: low, medium, high, production."),
    verify: bool = typer.Option(False, "--verify", help="Enable formal verification (off by default in explore)."),
    no_verify: bool = typer.Option(False, "--no-verify", help="Skip formal verification step (default in explore)."),
    verify_timeout: Optional[int] = typer.Option(None, "--verify-timeout", help="Verification timeout in seconds."),
    retry: bool = typer.Option(False, "--retry", help="Retry a previously failed exploration."),
    force: bool = typer.Option(False, "--force", help="Force re-run even if already completed."),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress non-essential output."),
    no_open: bool = typer.Option(False, "--no-open", help="Do not open the output file when done."),
    json_output: bool = typer.Option(False, "--json", help="Output result as JSON."),
) -> None:
    """Explore a math topic: plan → visualize → summarize.

    Verification is skipped by default in explore mode for speed.
    Use --verify to enable it, or use `mathlens deep` for full rigour.
    """
    install_signal_handlers()

    # Explore mode: skip verification by default unless --verify is passed
    skip_verify = not verify if not no_verify else True

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
            no_verify=skip_verify,
            no_open=no_open,
            quiet=quiet,
        )
        result = run_explore(query, settings, format_override=format, no_verify=skip_verify, quiet=quiet, force=force)
        display_result(result)
        if settings.ui.open_video_on_complete and not no_open:
            _auto_open_output(result)
    except KeyboardInterrupt:
        cleanup()
        console.print("\n  [dim]Interrupted. All background processes stopped.[/dim]")
        raise typer.Exit(code=130)
    except Exception as exc:
        cleanup()
        console.print(format_error(str(exc)))
        raise typer.Exit(code=1)
