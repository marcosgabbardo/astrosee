"""Watch mode command - live monitoring."""

import asyncio
from datetime import datetime

import click

from astrosee.cli.context import CliContext
from astrosee.core.exceptions import AstroseeError


pass_context = click.make_pass_decorator(CliContext)


@click.command()
@click.option(
    "--location", "-l",
    type=str,
    help="Location name (uses default if not specified)",
)
@click.option(
    "--interval", "-i",
    type=int,
    default=30,
    help="Update interval in minutes (default: 30)",
)
@click.option(
    "--target", "-t",
    type=str,
    help="Target object to track",
)
@pass_context
def watch(
    ctx: CliContext,
    location: str | None,
    interval: int,
    target: str | None,
) -> None:
    """Live monitoring of seeing conditions.

    Continuously updates the display with current conditions.
    Press Ctrl+C to stop.

    Examples:
        astrosee watch
        astrosee watch --interval 15
        astrosee watch --target Jupiter
    """
    asyncio.run(_watch_async(ctx, location, interval, target))


async def _watch_async(
    ctx: CliContext,
    location_name: str | None,
    interval: int,
    target_name: str | None,
) -> None:
    """Async implementation of watch command."""
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

        ctx.console.print(f"[bold]Watch Mode[/bold] - {loc.name}")
        ctx.console.print(f"Updating every {interval} minutes. Press Ctrl+C to stop.\n")

        update_count = 0

        while True:
            update_count += 1

            # Clear screen for clean update (optional)
            # ctx.console.clear()

            ctx.console.print(f"[dim]Update #{update_count} - {datetime.now().strftime('%H:%M:%S')}[/dim]")

            try:
                report = await seeing_service.get_current_conditions(loc, target_name)
                ctx.renderer.render_current_conditions(report)
            except AstroseeError as e:
                ctx.renderer.print_warning(f"Update failed: {e}")

            ctx.console.print(f"\n[dim]Next update in {interval} minutes...[/dim]")
            ctx.console.print("-" * 60)

            # Wait for next update
            await asyncio.sleep(interval * 60)

    except KeyboardInterrupt:
        ctx.console.print("\n[yellow]Watch mode stopped[/yellow]")
    except AstroseeError as e:
        ctx.renderer.print_error(str(e))
        raise SystemExit(1)
    finally:
        await ctx.cleanup()
