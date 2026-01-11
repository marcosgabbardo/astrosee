"""Main CLI entry point."""

import asyncio
from functools import wraps
from pathlib import Path
from typing import Any, Callable

import click
from rich.console import Console

from astrosee import __version__
from astrosee.cli.context import CliContext
from astrosee.core.exceptions import AstroseeError


# Pass context to commands
pass_context = click.make_pass_decorator(CliContext)


def async_command(f: Callable) -> Callable:
    """Decorator to run async Click commands."""
    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return asyncio.run(f(*args, **kwargs))
    return wrapper


@click.group()
@click.option(
    "--config-dir",
    type=click.Path(path_type=Path),
    help="Custom configuration directory",
)
@click.option(
    "-v", "--verbose",
    is_flag=True,
    help="Enable verbose output",
)
@click.version_option(version=__version__, prog_name="astrosee")
@click.pass_context
def cli(ctx: click.Context, config_dir: Path | None, verbose: bool) -> None:
    """Astrosee - Astronomical Seeing Prediction CLI.

    Predict observation quality based on atmospheric conditions.
    """
    ctx.obj = CliContext.create(config_dir=config_dir, verbose=verbose)


# Import and register commands
from astrosee.cli.commands import (
    advise,
    alert,
    best_window,
    compare,
    config,
    equipment,
    forecast,
    now,
    session,
    target,
    timelapse,
    watch,
    widget,
)

cli.add_command(config.config)
cli.add_command(now.now)
cli.add_command(forecast.forecast)
cli.add_command(target.target)
cli.add_command(best_window.best_window)
cli.add_command(watch.watch)
cli.add_command(compare.compare)
cli.add_command(alert.alert)
cli.add_command(widget.widget)
cli.add_command(session.session)
cli.add_command(equipment.equipment)
cli.add_command(timelapse.timelapse)
cli.add_command(advise.advise)


def main() -> None:
    """Main entry point."""
    try:
        cli()
    except AstroseeError as e:
        console = Console()
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)
    except KeyboardInterrupt:
        raise SystemExit(0)


if __name__ == "__main__":
    main()
