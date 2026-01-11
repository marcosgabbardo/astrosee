"""Best observation window command."""

import asyncio

import click

from astrosee.cli.context import CliContext
from astrosee.core.exceptions import AstroseeError


pass_context = click.make_pass_decorator(CliContext)


@click.command("best-window")
@click.option(
    "--location", "-l",
    type=str,
    help="Location name (uses default if not specified)",
)
@click.option(
    "--hours", "-h",
    type=int,
    default=48,
    help="Hours to search (default: 48)",
)
@click.option(
    "--min-score", "-s",
    type=float,
    default=50,
    help="Minimum acceptable score (default: 50)",
)
@click.option(
    "--min-duration", "-d",
    type=int,
    default=2,
    help="Minimum window duration in hours (default: 2)",
)
@pass_context
def best_window(
    ctx: CliContext,
    location: str | None,
    hours: int,
    min_score: float,
    min_duration: int,
) -> None:
    """Find the best observation window.

    Analyzes the forecast to find the optimal time period
    for observation based on seeing score.

    Examples:
        astrosee best-window
        astrosee best-window --hours 72 --min-score 70
        astrosee best-window --min-duration 4
    """
    asyncio.run(_best_window_async(ctx, location, hours, min_score, min_duration))


async def _best_window_async(
    ctx: CliContext,
    location_name: str | None,
    hours: int,
    min_score: float,
    min_duration: int,
) -> None:
    """Async implementation of best-window command."""
    try:
        # Get location
        if location_name:
            loc = ctx.config.get_location(location_name)
            if not loc:
                ctx.renderer.print_error(f"Location '{location_name}' not found")
                raise SystemExit(1)
        else:
            loc = ctx.config.get_default_location()
            if not loc:
                ctx.renderer.print_error(
                    "No default location set. Use 'astrosee config set' first."
                )
                raise SystemExit(1)

        forecast_service = ctx.get_forecast_service()

        ctx.console.print(f"Searching next {hours} hours for optimal window...")
        ctx.console.print(f"Criteria: score >= {min_score}, duration >= {min_duration}h")
        ctx.console.print()

        with ctx.console.status("Analyzing forecast..."):
            window = await forecast_service.find_best_window(
                location=loc,
                hours=hours,
                min_score=min_score,
                min_duration_hours=min_duration,
            )

        ctx.renderer.render_best_window(window)

        if window:
            # Show detailed forecast for the window
            ctx.console.print("\n[bold]Window Detail:[/bold]")
            ctx.renderer.render_forecast_table(
                window.forecasts,
                title="Observation Window Forecast",
            )

    except AstroseeError as e:
        ctx.renderer.print_error(str(e))
        raise SystemExit(1)
    finally:
        await ctx.cleanup()
