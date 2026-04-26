"""mathlens knowledge — history, search, and show commands."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from mathlens.cli.app import app
from mathlens.config.settings import MathLensSettings
from mathlens.models import Badge, StageStatus
from mathlens.ui.console import console, make_table
from mathlens.workspace.search import SearchIndex
from mathlens.workspace.store import WorkspaceStore

_CONFIG_PATH = Path.home() / ".config" / "mathlens" / "config.toml"


def _get_workspace_root() -> Path:
    """Load settings and return the expanded workspace path."""
    settings = MathLensSettings.from_toml(_CONFIG_PATH)
    return Path(settings.workspace.path).expanduser()


@app.command()
def history(
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum number of explorations to show."),
) -> None:
    """List past explorations."""
    ws_root = _get_workspace_root()
    store = WorkspaceStore(ws_root)
    explorations = store.list_explorations()[:limit]

    if not explorations:
        console.print("[dim]No explorations yet.[/dim]")
        return

    table, panel = make_table("Explorations", [("Topic", None), ("Mode", None), ("Status", None), ("Slug", "dim")])

    for meta in explorations:
        status_style = "green" if meta.status == StageStatus.completed else "yellow"
        table.add_row(
            meta.topic,
            meta.mode.value,
            f"[{status_style}]{meta.status.value}[/{status_style}]",
            meta.slug,
        )

    console.print(panel)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query."),
) -> None:
    """Search past explorations using full-text search."""
    ws_root = _get_workspace_root()
    store = WorkspaceStore(ws_root)
    db_path = ws_root / "search.db"
    index = SearchIndex(db_path)

    # Auto-index any un-indexed explorations
    for meta in store.list_explorations():
        ws_dir = store.path_for(meta.slug)
        index.index_exploration(meta.slug, ws_dir)

    results = index.search(query)
    index.close()

    if not results:
        console.print("[dim]No results.[/dim]")
        return

    table, panel = make_table(f"Search: {query}", [("Topic", None), ("Match", "dim")])

    for result in results:
        table.add_row(result.topic, result.snippet)

    console.print(panel)


@app.command()
def show(
    topic: str = typer.Argument(..., help="Topic name or slug to display."),
) -> None:
    """Show details of a past exploration."""
    ws_root = _get_workspace_root()
    store = WorkspaceStore(ws_root)

    # Try exact topic match first
    meta = store.find_by_topic(topic)

    # Fall back to substring matching against slug and topic
    if meta is None:
        for candidate in store.list_explorations():
            if topic.lower() in candidate.slug.lower() or topic.lower() in candidate.topic.lower():
                meta = candidate
                break

    if meta is None:
        console.print(f"[red]Not found:[/red] {topic!r}")
        raise typer.Exit(code=1)

    # Display header and metadata
    console.print(f"[bold]{meta.topic}[/bold]")
    console.print(f"  Mode:   {meta.mode.value}")
    console.print(f"  Status: {meta.status.value}")
    console.print(f"  Slug:   {meta.slug}")

    ws_dir = store.path_for(meta.slug)

    # Display summary if exists
    summary_path = ws_dir / "summary.md"
    if summary_path.exists():
        console.print()
        console.print("[bold]Summary[/bold]")
        console.print(summary_path.read_text())

    # Show video if it exists
    output_dir = ws_dir / "output"
    video = None
    if output_dir.is_dir():
        for f in output_dir.glob("**/*.mp4"):
            if "partial_movie_files" not in str(f):
                video = f
                break
    if video:
        console.print()
        console.print(f"[green]Video:[/green] {video}")

    # List artifacts with file sizes
    artifacts = [
        p for p in ws_dir.iterdir()
        if p.is_file() and p.name != "meta.json"
    ]
    if artifacts:
        console.print()
        console.print("[bold]Artifacts[/bold]")
        for artifact in sorted(artifacts, key=lambda p: p.name):
            size = artifact.stat().st_size
            console.print(f"  {artifact.name}  [dim]{size} bytes[/dim]")
