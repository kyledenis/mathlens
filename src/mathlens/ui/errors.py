"""Human-readable error formatting."""


def format_error(message: str, hint: str | None = None) -> str:
    parts = [f"[red bold]Error:[/red bold] {message}"]
    if hint:
        parts.append(f"[dim]Hint: {hint}[/dim]")
    return "\n".join(parts)


def format_refuted_error(failure_reason: str, lean_output: str) -> str:
    lines = [
        "[red bold]Mathematics refuted[/red bold]",
        "",
        f"  {failure_reason}",
        "",
        "  The formal verifier found this statement to be mathematically incorrect.",
        "  Visualization has been halted to prevent showing wrong mathematics.",
    ]
    if lean_output:
        lines.extend([
            "",
            "[dim]Lean output:[/dim]",
            f"  [dim]{lean_output[:300]}[/dim]",
        ])
    return "\n".join(lines)
