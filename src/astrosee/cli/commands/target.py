"""Target object command."""

import asyncio

import click

from astrosee.cli.context import CliContext
from astrosee.core.exceptions import AstroseeError, CatalogNotFoundError


pass_context = click.make_pass_decorator(CliContext)


@click.command()
@click.argument("name")
@click.option(
    "--location", "-l",
    type=str,
    help="Location name (uses default if not specified)",
)
@click.option(
    "--hours", "-h",
    type=int,
    default=24,
    help="Hours to show visibility (default: 24)",
)
@pass_context
def target(
    ctx: CliContext,
    name: str,
    location: str | None,
    hours: int,
) -> None:
    """Show conditions for a specific target.

    Displays current position, airmass, and visibility forecast
    for a celestial object.

    Examples:
        astrosee target Jupiter
        astrosee target M42 --hours 48
        astrosee target "Orion Nebula" --location "Dark Site"
    """
    asyncio.run(_target_async(ctx, name, location, hours))


async def _target_async(
    ctx: CliContext,
    target_name: str,
    location_name: str | None,
    hours: int,
) -> None:
    """Async implementation of target command."""
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

        seeing_service = ctx.get_seeing_service()
        forecast_service = ctx.get_forecast_service()

        # Search for target
        target_obj = seeing_service.catalog.search(target_name)
        if not target_obj:
            ctx.renderer.print_error(f"Target '{target_name}' not found in catalog")

            # Suggest similar objects
            similar = seeing_service.catalog.search_all(target_name[:3])[:5]
            if similar:
                ctx.console.print("\nDid you mean:")
                for obj in similar:
                    ctx.console.print(f"  - {obj.name} ({obj.designation})")

            raise SystemExit(1)

        # Get current conditions for target
        with ctx.console.status(f"Analyzing {target_obj.name}..."):
            report = await seeing_service.get_current_conditions(loc, target_obj)

        # Display current status
        ctx.console.print(f"\n[bold]Target: {target_obj.name}[/bold] ({target_obj.designation})")
        if target_obj.description:
            ctx.console.print(f"[dim]{target_obj.description}[/dim]")
        ctx.console.print()

        if report.target_position:
            pos = report.target_position
            if pos.is_visible:
                ctx.console.print(f"Current Status:")
                ctx.console.print(f"  Altitude: {pos.altitude:.1f}°")
                ctx.console.print(f"  Azimuth: {pos.azimuth:.1f}°")
                ctx.console.print(f"  Airmass: {pos.airmass:.2f} ({pos.airmass_quality})")
                if target_obj.magnitude:
                    ctx.console.print(f"  Magnitude: {target_obj.magnitude:.1f}")
            else:
                ctx.console.print("[yellow]Currently below horizon[/yellow]")

        ctx.console.print()
        ctx.console.print(
            f"Seeing Score for {target_obj.name}: "
            f"{report.score.total_score:.0f}/100 ({report.score.rating})"
        )
        ctx.console.print()

        # Get visibility forecast
        with ctx.console.status("Generating visibility forecast..."):
            visibility = await forecast_service.get_target_visibility(
                loc, target_name, hours
            )

        if visibility:
            ctx.renderer.render_target_visibility(target_obj.name, visibility)

    except CatalogNotFoundError as e:
        ctx.renderer.print_error(str(e))
        raise SystemExit(1)
    except AstroseeError as e:
        ctx.renderer.print_error(str(e))
        raise SystemExit(1)
    finally:
        await ctx.cleanup()
