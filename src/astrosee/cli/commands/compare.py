"""Location comparison command."""

import asyncio

import click

from astrosee.cli.context import CliContext
from astrosee.core.exceptions import AstroseeError


pass_context = click.make_pass_decorator(CliContext)


@click.command()
@click.option(
    "--locations", "-l",
    type=str,
    required=True,
    help="Comma-separated list of location names",
)
@pass_context
def compare(ctx: CliContext, locations: str) -> None:
    """Compare seeing conditions at multiple locations.

    Compares current conditions across saved locations
    to help choose the best observing site.

    Examples:
        astrosee compare --locations "Home,Dark Site,Mountain"
        astrosee compare -l "Criciuma,Urubici,Sao Joaquim"
    """
    asyncio.run(_compare_async(ctx, locations))


async def _compare_async(ctx: CliContext, locations_str: str) -> None:
    """Async implementation of compare command."""
    try:
        # Parse location names
        location_names = [name.strip() for name in locations_str.split(",")]

        if len(location_names) < 2:
            ctx.renderer.print_error("Please provide at least 2 locations to compare")
            raise SystemExit(1)

        # Resolve locations
        locations = []
        for name in location_names:
            loc = ctx.config.get_location(name)
            if not loc:
                ctx.renderer.print_error(f"Location '{name}' not found")
                ctx.console.print("Available locations:")
                for saved_name in ctx.config.get_all_locations():
                    ctx.console.print(f"  - {saved_name}")
                raise SystemExit(1)
            locations.append(loc)

        forecast_service = ctx.get_forecast_service()

        with ctx.console.status(f"Comparing {len(locations)} locations..."):
            comparison = await forecast_service.compare_locations(locations)

        ctx.renderer.render_location_comparison(comparison)

        # Show additional details for best location
        best_loc, best_report = comparison.best_location
        ctx.console.print(f"\n[bold]Best Location Details - {best_loc.name}[/bold]")
        ctx.console.print(f"  Cloud cover: {best_report.weather.cloud_cover:.0f}%")
        ctx.console.print(f"  Wind: {best_report.weather.wind_speed_10m * 3.6:.1f} km/h")
        ctx.console.print(f"  Humidity: {best_report.weather.humidity:.0f}%")
        ctx.console.print(f"  Moon: {best_report.astronomy.moon_phase}")

    except AstroseeError as e:
        ctx.renderer.print_error(str(e))
        raise SystemExit(1)
    finally:
        await ctx.cleanup()
