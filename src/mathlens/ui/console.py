"""Rich console singleton and helpers."""

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from mathlens.models import Badge

console = Console()


def make_table(title: str, columns: list[tuple[str, str | None]]) -> tuple[Table, Panel]:
    """Create a table wrapped in a Panel with title embedded in the border.

    Returns (table, panel).  Add rows to *table*, then ``console.print(panel)``.

    *columns* is a list of ``(header, style)`` pairs.
    """
    table = Table(
        show_header=True,
        header_style="bold dim",
        box=None,             # no table border — the Panel provides it
        expand=True,
        padding=(0, 1),
        show_edge=False,
    )
    for header, style in columns:
        table.add_column(header, style=style or "")

    panel = Panel(
        table,
        title=f" {title} ",
        title_align="left",
        border_style="dim",
        box=box.ROUNDED,
        padding=(0, 0),
    )
    return table, panel


def format_badge(badge: Badge) -> str:
    return badge.icon


def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes}m {secs:.0f}s"


def format_topic_header(topic: str) -> str:
    title = topic.replace("-", " ").title()
    return f"[bold]{title}[/bold]"
