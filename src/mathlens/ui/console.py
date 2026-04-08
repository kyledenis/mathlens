"""Rich console singleton and helpers."""

from rich.console import Console

from mathlens.models import Badge

console = Console()


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
