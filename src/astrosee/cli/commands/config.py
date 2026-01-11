"""Configuration command."""

import click
from rich.table import Table

from astrosee.cli.context import CliContext


pass_context = click.make_pass_decorator(CliContext)


@click.group()
def config() -> None:
    """Manage configuration and locations."""
    pass


@config.command("set")
@click.option("--lat", type=float, required=True, help="Latitude in degrees")
@click.option("--lon", type=float, required=True, help="Longitude in degrees")
@click.option("--name", type=str, required=True, help="Location name")
@click.option("--elevation", type=float, default=0, help="Elevation in meters")
@click.option("--timezone", type=str, default="UTC", help="Timezone name")
@pass_context
def set_location(
    ctx: CliContext,
    lat: float,
    lon: float,
    name: str,
    elevation: float,
    timezone: str,
) -> None:
    """Set a location for observation.

    Example: astrosee config set --lat -29.18 --lon -49.64 --name "Criciuma"
    """
    try:
        location = ctx.config.add_location(
            name=name,
            latitude=lat,
            longitude=lon,
            elevation=elevation,
            timezone=timezone,
            set_default=True,
        )
        ctx.renderer.print_success(
            f"Location '{name}' saved at ({lat:.4f}, {lon:.4f})"
        )
        ctx.renderer.print_success(f"Set as default location")
    except Exception as e:
        ctx.renderer.print_error(f"Failed to save location: {e}")
        raise SystemExit(1)


@config.command("list")
@pass_context
def list_locations(ctx: CliContext) -> None:
    """List all saved locations."""
    locations = ctx.config.get_all_locations()
    default_loc = ctx.config.get_default_location()

    if not locations:
        ctx.renderer.print_warning("No locations configured.")
        ctx.console.print("Use 'astrosee config set' to add a location.")
        return

    table = Table(title="Saved Locations")
    table.add_column("Name", style="cyan")
    table.add_column("Latitude")
    table.add_column("Longitude")
    table.add_column("Elevation")
    table.add_column("Default", justify="center")

    for name, loc in locations.items():
        is_default = "✓" if default_loc and loc.name == default_loc.name else ""
        table.add_row(
            name,
            f"{loc.latitude:.4f}",
            f"{loc.longitude:.4f}",
            f"{loc.elevation:.0f}m",
            is_default,
        )

    ctx.console.print(table)


@config.command("remove")
@click.argument("name")
@pass_context
def remove_location(ctx: CliContext, name: str) -> None:
    """Remove a saved location."""
    if ctx.config.remove_location(name):
        ctx.renderer.print_success(f"Location '{name}' removed")
    else:
        ctx.renderer.print_error(f"Location '{name}' not found")
        raise SystemExit(1)


@config.command("default")
@click.argument("name")
@pass_context
def set_default(ctx: CliContext, name: str) -> None:
    """Set the default location."""
    try:
        ctx.config.set_default_location(name)
        ctx.renderer.print_success(f"Default location set to '{name}'")
    except Exception as e:
        ctx.renderer.print_error(str(e))
        raise SystemExit(1)


@config.command("show")
@pass_context
def show_config(ctx: CliContext) -> None:
    """Show current configuration."""
    ctx.console.print(f"[bold]Configuration Directory:[/bold] {ctx.config.config_dir}")
    ctx.console.print(f"[bold]Cache Database:[/bold] {ctx.config.cache_db_path}")
    ctx.console.print()

    default_loc = ctx.config.get_default_location()
    if default_loc:
        ctx.console.print(f"[bold]Default Location:[/bold] {default_loc}")
    else:
        ctx.console.print("[yellow]No default location set[/yellow]")

    ctx.console.print()
    ctx.console.print("[bold]Settings:[/bold]")
    ctx.console.print(f"  Cache TTL: {ctx.config.cache_ttl_hours} hours")
    ctx.console.print(f"  Default forecast: {ctx.config.default_forecast_hours} hours")
