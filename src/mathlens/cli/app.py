"""Main MathLens CLI application."""
from __future__ import annotations
import typer
from mathlens import __version__

app = typer.Typer(
    name="mathlens",
    help="Verify, then visualize. Learn math you can trust.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"mathlens {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", "-V", callback=version_callback, is_eager=True, help="Show version."),
) -> None:
    """MathLens — Verify, then visualize. Learn math you can trust."""


# Register commands
from mathlens.cli import explore as _explore  # noqa: F401, E402
try:
    from mathlens.cli import deep as _deep  # noqa: F401, E402
except (ImportError, AttributeError):
    pass
try:
    from mathlens.cli import tools as _tools  # noqa: F401, E402
except (ImportError, AttributeError):
    pass
try:
    from mathlens.cli import config_cmd as _config  # noqa: F401, E402
except (ImportError, AttributeError):
    pass
try:
    from mathlens.cli import doctor as _doctor  # noqa: F401, E402
except (ImportError, AttributeError):
    pass
try:
    from mathlens.cli import knowledge as _knowledge  # noqa: F401, E402
except (ImportError, AttributeError):
    pass
