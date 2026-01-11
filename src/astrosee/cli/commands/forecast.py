"""Forecast command."""

import asyncio
from datetime import datetime

import click

from astrosee.cli.context import CliContext
from astrosee.core.exceptions import AstroseeError
from astrosee.display.charts import ChartRenderer


pass_context = click.make_pass_decorator(CliContext)


@click.command()
@click.option(
    "--location", "-l",
    type=str,
    help="Location name (uses default if not specified)",
)
@click.option(
    "--hours", "-h",
    type=int,
    default=168,
    help="Number of hours to forecast (default: 168 = 7 days)",
)
@click.option(
    "--daily/--hourly",
    default=True,
    help="Show daily summary (default) or hourly detail",
)
@click.option(
    "--chart/--no-chart",
    default=True,
    help="Show score trend chart",
)
@pass_context
def forecast(
    ctx: CliContext,
    location: str | None,
    hours: int,
    daily: bool,
    chart: bool,
) -> None:
    """Show seeing forecast.

    Displays predicted seeing conditions for the next 7 days (default)
    with daily summaries and optional trend chart.

    Examples:
        astrosee forecast
        astrosee forecast --hours 48 --hourly
        astrosee forecast --no-chart
    """
    asyncio.run(_forecast_async(ctx, location, hours, daily, chart))


async def _forecast_async(
    ctx: CliContext,
    location_name: str | None,
    hours: int,
    daily: bool,
    show_chart: bool,
) -> None:
    """Async implementation of forecast command."""
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
        seeing_service = ctx.get_seeing_service()

        with ctx.console.status("Fetching forecast..."):
            forecasts = await seeing_service.get_forecast(loc, hours)

        if not forecasts:
            ctx.renderer.print_warning("No forecast data available")
            return

        # Show chart if requested
        if show_chart and len(forecasts) > 1:
            chart_renderer = ChartRenderer()
            chart_str = chart_renderer.render_score_timeline(forecasts)
            ctx.console.print("\n[bold]Score Trend[/bold]")
            ctx.console.print(chart_str)
            ctx.console.print()

        if daily:
            # Get best nights summary
            best_nights = await forecast_service.get_best_nights(
                loc, days=hours // 24, min_score=0
            )
            ctx.renderer.render_daily_forecast(best_nights)
        else:
            # Show hourly detail
            # Filter to nighttime hours for clarity
            night_forecasts = [f for f in forecasts if f.is_night]
            if night_forecasts:
                ctx.renderer.render_forecast_table(
                    night_forecasts[:48],  # Limit to 48 entries
                    title=f"Nighttime Forecast - {loc.name}",
                )
            else:
                ctx.renderer.render_forecast_table(
                    forecasts[:24],
                    title=f"Forecast - {loc.name}",
                )

    except AstroseeError as e:
        ctx.renderer.print_error(str(e))
        raise SystemExit(1)
    finally:
        await ctx.cleanup()
