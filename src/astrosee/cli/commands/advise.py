"""Equipment advisor command."""

import asyncio
from datetime import datetime, timezone

import click
from rich.panel import Panel
from rich.table import Table

from astrosee.cli.context import CliContext
from astrosee.core.exceptions import AstroseeError
from astrosee.display.formatters import format_score_bar
from astrosee.services.advisor import AdvisorService


pass_context = click.make_pass_decorator(CliContext)


@click.command()
@click.option(
    "--location",
    "-l",
    type=str,
    help="Location name (uses default if not specified)",
)
@click.option(
    "--activity",
    "-a",
    type=click.Choice(["visual", "planetary_imaging", "deep_sky_imaging", "widefield"]),
    help="Focus on specific activity type",
)
@click.option(
    "--target",
    "-t",
    type=str,
    help="Get advice for a specific target",
)
@pass_context
def advise(
    ctx: CliContext,
    location: str | None,
    activity: str | None,
    target: str | None,
) -> None:
    """Get equipment and activity recommendations.

    Analyzes current conditions and suggests the best activities,
    equipment setup, and targets for tonight.

    \\b
    Examples:
        astrosee advise
        astrosee advise --activity planetary_imaging
        astrosee advise --target "Jupiter"
    """
    asyncio.run(_advise_async(ctx, location, activity, target))


async def _advise_async(
    ctx: CliContext,
    location_name: str | None,
    activity_filter: str | None,
    target_name: str | None,
) -> None:
    """Async implementation of advise command."""
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

        # Get current conditions
        seeing_service = ctx.get_seeing_service()

        with ctx.console.status("Analyzing conditions..."):
            report = await seeing_service.get_current_conditions(
                location=loc,
                target=target_name,
            )

        # Create advisor service
        advisor = AdvisorService(
            calculator=seeing_service.astronomy,
            catalog=seeing_service.catalog,
        )

        console = ctx.console
        console.print()

        # Header
        console.print(Panel("Equipment Advisor", style="bold cyan"))
        console.print()

        # Current conditions summary
        score = report.score.total_score
        weather = report.weather
        moon = report.astronomy

        conditions = (
            f"Wind: {weather.wind_speed_10m or 0:.0f} m/s | "
            f"Clouds: {weather.cloud_cover or 0:.0f}% | "
            f"Moon: {moon.moon_illumination:.0f}%"
        )
        if moon.moon_altitude <= 0:
            conditions += " (below horizon)"

        console.print(
            f"[bold]Current Conditions:[/] {score:.0f}/100 ({report.score.rating})"
        )
        console.print(f"  [dim]{conditions}[/]")
        console.print()

        # Activity recommendations
        activities = advisor.get_activity_recommendations(report)
        _render_activities(ctx, activities, activity_filter)

        # Equipment suggestions
        suggestions = advisor.get_equipment_suggestions(report)
        _render_suggestions(ctx, suggestions)

        # Target recommendations
        now = datetime.now(timezone.utc)
        targets = advisor.get_target_recommendations(report, loc, now)
        if targets:
            _render_targets(ctx, targets)

    except AstroseeError as e:
        ctx.renderer.print_error(str(e))
        raise SystemExit(1)
    finally:
        await ctx.cleanup()


def _render_activities(ctx: CliContext, activities, filter_activity: str | None):
    """Render activity recommendations."""
    console = ctx.console
    console.print("[bold]✅ Activity Recommendations:[/]")

    activity_names = {
        "visual": "Visual observation",
        "planetary_imaging": "Planetary imaging",
        "deep_sky_imaging": "Deep-sky imaging",
        "widefield": "Widefield photography",
    }

    for act in activities:
        if filter_activity and act.activity != filter_activity:
            continue

        name = activity_names.get(act.activity, act.activity)
        bar = format_score_bar(act.score, width=20)

        # Color based on rating
        if act.score >= 70:
            rating_str = f"[green]{act.rating}[/]"
        elif act.score >= 50:
            rating_str = f"[yellow]{act.rating}[/]"
        else:
            rating_str = f"[red]{act.rating}[/]"

        console.print(f"  • {name:22} {bar} {rating_str}")

        if act.issues and (filter_activity == act.activity or act.score < 50):
            for issue in act.issues:
                console.print(f"    [dim]↳ {issue}[/]")

    console.print()


def _render_suggestions(ctx: CliContext, suggestions):
    """Render equipment suggestions."""
    console = ctx.console

    if not suggestions:
        return

    console.print("[bold]📝 Equipment Suggestions:[/]")
    for sug in suggestions:
        if sug.priority == "high":
            console.print(f"  {sug.icon} [bold]{sug.text}[/]")
        elif sug.priority == "medium":
            console.print(f"  {sug.icon} {sug.text}")
        else:
            console.print(f"  {sug.icon} [dim]{sug.text}[/]")

    console.print()


def _render_targets(ctx: CliContext, targets):
    """Render target recommendations."""
    console = ctx.console
    console.print("[bold]🎯 Tonight's Best Targets:[/]")

    activity_labels = {
        "planetary": "Planetary",
        "deep_sky": "Deep-sky",
        "visual": "Visual",
    }

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Name", style="cyan")
    table.add_column("Alt", justify="right")
    table.add_column("Score", justify="right")
    table.add_column("Type", style="dim")

    for t in targets:
        name = t.name
        if t.description:
            name += f" ({t.description})"

        table.add_row(
            name[:30],
            f"{t.altitude:.0f}°",
            f"{t.score:.0f}",
            activity_labels.get(t.activity_type, t.activity_type),
        )

    console.print(table)
    console.print()
