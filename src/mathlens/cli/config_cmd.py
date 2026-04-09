"""mathlens config — configuration management."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer
from mathlens.cli.app import app
from mathlens.config.profiles import ProfileManager
from mathlens.config.settings import MathLensSettings
from mathlens.ui.console import console, make_table

DEFAULT_CONFIG = Path.home() / ".config" / "mathlens" / "config.toml"

config_app = typer.Typer(name="config", help="Manage MathLens configuration.", no_args_is_help=True)
app.add_typer(config_app)


def _load(path: Path) -> MathLensSettings:
    return MathLensSettings.from_toml(path)


def _save(settings: MathLensSettings, path: Path) -> None:
    settings.save_toml(path)


def _coerce(value: str) -> object:
    """Coerce a string value to bool or int where appropriate."""
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.lstrip("-").isdigit():
        return int(value)
    return value


# ---------------------------------------------------------------------------
# config show
# ---------------------------------------------------------------------------

@config_app.command("show")
def config_show(
    config_path: Path = typer.Option(DEFAULT_CONFIG, "--config-path", hidden=True),
) -> None:
    """Display current configuration as a table."""
    settings = _load(config_path)

    table, panel = make_table("Configuration", [("Key", "bold"), ("Value", None)])

    table.add_row("provider.default", str(settings.provider.default))
    table.add_row("provider.fallback_chain", str(settings.provider.fallback_chain))
    table.add_row("provider.cli.backend", str(settings.provider.cli.backend))
    table.add_row("provider.api.model", str(settings.provider.api.model))
    table.add_row("provider.local.model", str(settings.provider.local.model))
    table.add_row("render.default_quality", str(settings.render.default_quality))
    table.add_row("render.default_format", str(settings.render.default_format))
    table.add_row("verification.always_attempt", str(settings.verification.always_attempt))
    table.add_row("workspace.path", str(settings.workspace.path))

    console.print(panel)


# ---------------------------------------------------------------------------
# config set
# ---------------------------------------------------------------------------

@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Dot-path settings key, e.g. provider.default"),
    value: str = typer.Argument(..., help="Value to set."),
    config_path: Path = typer.Option(DEFAULT_CONFIG, "--config-path", hidden=True),
) -> None:
    """Set a configuration value by dot-path key."""
    settings = _load(config_path)
    coerced = _coerce(value)
    try:
        settings.set(key, coerced)
    except KeyError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)
    _save(settings, config_path)
    console.print(f"[green]Set[/green] {key} = {coerced!r}")


# ---------------------------------------------------------------------------
# config diff
# ---------------------------------------------------------------------------

@config_app.command("diff")
def config_diff(
    config_path: Path = typer.Option(DEFAULT_CONFIG, "--config-path", hidden=True),
) -> None:
    """Show settings that differ from defaults."""
    settings = _load(config_path)
    changes = settings.diff()

    if not changes:
        console.print("No changes from defaults.")
        return

    table, panel = make_table("Configuration Diff", [("Key", "bold"), ("Default", None), ("Current", "green")])

    for dot_path, info in changes.items():
        table.add_row(dot_path, str(info["default"]), str(info["current"]))

    console.print(panel)


# ---------------------------------------------------------------------------
# config reset
# ---------------------------------------------------------------------------

@config_app.command("reset")
def config_reset(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
    config_path: Path = typer.Option(DEFAULT_CONFIG, "--config-path", hidden=True),
) -> None:
    """Reset configuration to factory defaults."""
    if not yes:
        typer.confirm("Reset all settings to defaults?", abort=True)
    fresh = MathLensSettings()
    _save(fresh, config_path)
    console.print("[green]Configuration reset to defaults.[/green]")


# ---------------------------------------------------------------------------
# config profile
# ---------------------------------------------------------------------------

@config_app.command("profile")
def config_profile(
    name: str = typer.Argument(..., help="Profile name to apply, e.g. personal or publish."),
    config_path: Path = typer.Option(DEFAULT_CONFIG, "--config-path", hidden=True),
) -> None:
    """Apply a named configuration profile."""
    settings = _load(config_path)
    manager = ProfileManager(config_path)
    try:
        manager.apply(name, settings)
    except KeyError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)
    _save(settings, config_path)
    console.print(f"[green]Applied profile:[/green] {name}")


# ---------------------------------------------------------------------------
# config edit
# ---------------------------------------------------------------------------

@config_app.command("edit")
def config_edit(
    config_path: Path = typer.Option(DEFAULT_CONFIG, "--config-path", hidden=True),
) -> None:
    """Open configuration file in $EDITOR."""
    if not config_path.exists():
        MathLensSettings().save_toml(config_path)
        console.print(f"[dim]Created default config at {config_path}[/dim]")

    editor = os.environ.get("EDITOR", "vim")
    try:
        subprocess.run([editor, str(config_path)], check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        console.print(f"[red]Error opening editor:[/red] {exc}")
        raise typer.Exit(code=1)
