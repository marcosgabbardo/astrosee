"""Current conditions command."""

import asyncio

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
    "--target", "-t",
    type=str,
    help="Target object name (e.g., 'Jupiter', 'M31')",
)
@pass_context
def now(ctx: CliContext, location: str | None, target: str | None) -> None:
    """Show current seeing conditions.

    Displays the current seeing score, weather conditions, moon phase,
    and observation recommendations.

    Examples:
        astrosee now
        astrosee now --target Jupiter
        astrosee now --location "Dark Site" --target M42
    """
    asyncio.run(_now_async(ctx, location, target))


async def _now_async(
    ctx: CliContext,
    location_name: str | None,
    target_name: str | None,
) -> None:
    """Async implementation of now command."""
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

        # Get seeing report
        seeing_service = ctx.get_seeing_service()

        with ctx.console.status("Fetching conditions..."):
            report = await seeing_service.get_current_conditions(
                location=loc,
                target=target_name,
            )

        # Display results
        ctx.renderer.render_current_conditions(report)

    except AstroseeError as e:
        ctx.renderer.print_error(str(e))
        raise SystemExit(1)
    finally:
        await ctx.cleanup()
