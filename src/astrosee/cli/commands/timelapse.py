"""Timelapse imaging planner command."""

import asyncio
import re
from datetime import datetime

import click
from rich.panel import Panel
from rich.table import Table

from astrosee.cli.context import CliContext
from astrosee.core.exceptions import AstroseeError
from astrosee.display.charts import ChartRenderer
from astrosee.services.timelapse import TimelapseService


pass_context = click.make_pass_decorator(CliContext)


def parse_duration(duration_str: str) -> float:
    """Parse duration string like '4h', '2h30m' to hours.

    Args:
        duration_str: Duration string (e.g., '4h', '2h30m', '90m')

    Returns:
        Duration in hours
    """
    duration_str = duration_str.lower().strip()

    # Try to parse hours and minutes
    hours = 0.0
    minutes = 0.0

    # Match patterns like "4h", "4h30m", "30m", "4.5h"
    hour_match = re.search(r"(\d+\.?\d*)h", duration_str)
    min_match = re.search(r"(\d+)m", duration_str)

    if hour_match:
        hours = float(hour_match.group(1))
    if min_match:
        minutes = float(min_match.group(1))

    if hours == 0 and minutes == 0:
        # Try parsing as plain number (assume hours)
        try:
            hours = float(duration_str.replace("h", "").replace("m", ""))
        except ValueError:
            hours = 4.0  # Default

    return hours + minutes / 60


@click.command()
@click.argument("target")
@click.option(
    "--duration", "-d",
    type=str,
    default="4h",
    help="Minimum session duration (e.g., '4h', '2h30m', '90m')",
)
@click.option(
    "--min-altitude", "-a",
    type=float,
    default=30.0,
    help="Minimum target altitude in degrees",
)
@click.option(
    "--date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Specific date to plan for (YYYY-MM-DD)",
)
@click.option(
    "--days",
    type=int,
    default=7,
    help="Days to search ahead",
)
@click.option(
    "--min-score",
    type=float,
    default=40.0,
    help="Minimum seeing score threshold",
)
@click.option(
    "--location", "-l",
    type=str,
    help="Location name (uses default if not specified)",
)
@pass_context
def timelapse(
    ctx: CliContext,
    target: str,
    duration: str,
    min_altitude: float,
    date: datetime | None,
    days: int,
    min_score: float,
    location: str | None,
) -> None:
    """Plan a timelapse imaging session for a target.

    Finds optimal windows when TARGET is above minimum altitude
    with good seeing conditions throughout.

    \b
    Examples:
        astrosee timelapse "M42" --duration 4h
        astrosee timelapse "M31" --date 2024-01-20 --duration 6h
        astrosee timelapse "Andromeda" -d 3h -a 40
        astrosee timelapse "Jupiter" -d 2h --min-score 60
    """
    asyncio.run(_timelapse_async(
        ctx, target, duration, min_altitude, date, days, min_score, location
    ))


async def _timelapse_async(
    ctx: CliContext,
    target: str,
    duration_str: str,
    min_altitude: float,
    target_date: datetime | None,
    days: int,
    min_score: float,
    location_name: str | None,
) -> None:
    """Async implementation of timelapse command."""
    try:
        # Parse duration
        duration_hours = parse_duration(duration_str)

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

        # Create timelapse service
        seeing_service = ctx.get_seeing_service()
        timelapse_service = TimelapseService(seeing_service)

        # Find windows
        with ctx.console.status(f"Finding imaging windows for {target}..."):
            windows = await timelapse_service.find_imaging_windows(
                target_name=target,
                location=loc,
                duration_hours=duration_hours,
                min_altitude=min_altitude,
                search_days=days,
                target_date=target_date,
                min_score=min_score,
            )

        if not windows:
            ctx.console.print()
            ctx.console.print(f"[yellow]No suitable imaging windows found for {target}[/]")
            ctx.console.print()
            ctx.console.print("[dim]Try:[/]")
            ctx.console.print(f"  - Lowering minimum altitude (current: {min_altitude}°)")
            ctx.console.print(f"  - Reducing minimum duration (current: {duration_str})")
            ctx.console.print(f"  - Lowering minimum score (current: {min_score})")
            ctx.console.print(f"  - Extending search period (current: {days} days)")
            return

        # Display best window
        best = windows[0]
        _render_best_window(ctx, best, min_altitude)

        # Display alternatives if available
        if len(windows) > 1:
            _render_alternatives(ctx, windows[1:5])  # Show up to 4 alternatives

    except AstroseeError as e:
        ctx.renderer.print_error(str(e))
        raise SystemExit(1)
    finally:
        await ctx.cleanup()


def _render_best_window(ctx: CliContext, window, min_altitude: float) -> None:
    """Render the best imaging window."""
    console = ctx.console

    # Header
    title = f"Timelapse Planning: {window.target_name}"
    if window.target_description:
        title += f" ({window.target_description})"

    console.print()
    console.print(Panel(title, style="bold cyan"))

    # Best window info
    date_str = window.date.strftime("%A, %b %d")
    console.print()
    console.print(f"[bold green]\U0001F4C5 Best Window:[/] {date_str}")
    console.print()

    # Window details
    console.print(f"  [bold]Start:[/]    {window.start.strftime('%H:%M')} "
                  f"(Alt: {window.start_altitude:.0f}°, Az: {window.start_azimuth:.0f}°)")
    console.print(f"  [bold]End:[/]      {window.end.strftime('%H:%M')} "
                  f"(Alt: {window.end_altitude:.0f}°, Az: {window.end_azimuth:.0f}°)")
    console.print(f"  [bold]Duration:[/] {window.duration_str}")
    console.print()

    # Peak altitude
    console.print(f"  [bold]Peak:[/]     {window.peak_time.strftime('%H:%M')} "
                  f"(Alt: {window.peak_altitude:.0f}°)")
    console.print()

    # Score info
    score_color = "green" if window.average_score >= 70 else "yellow" if window.average_score >= 50 else "red"
    console.print(f"  [bold]Average Score:[/] [{score_color}]{window.average_score:.0f}/100[/]")
    console.print(f"  [bold]Score Range:[/]   {window.min_score:.0f} - {window.max_score:.0f}")
    console.print()

    # Altitude profile chart
    chart_renderer = ChartRenderer()
    chart = chart_renderer.render_altitude_profile(
        window.altitude_profile,
        min_altitude=min_altitude,
        width=50,
        height=8,
    )
    console.print("  [bold]Altitude Profile:[/]")
    for line in chart.split("\n"):
        console.print(f"  {line}")
    console.print()

    # Moon interference
    if window.moon_interference:
        moon = window.moon_interference
        _render_moon_warning(ctx, moon)


def _render_moon_warning(ctx: CliContext, moon) -> None:
    """Render moon interference warning."""
    console = ctx.console

    if moon.severity == "none":
        console.print(f"[green]\U0001F319 Moon:[/] {moon.illumination:.0f}% illuminated (below horizon)")
        console.print()
        return

    # Moon warning
    severity_colors = {
        "minor": "yellow",
        "moderate": "yellow",
        "severe": "red",
    }
    color = severity_colors.get(moon.severity, "yellow")

    console.print(f"[{color}]\U0001F319 Moon Warning:[/]")

    if moon.rises_at:
        console.print(f"  Moon rises at {moon.rises_at.strftime('%H:%M')} "
                      f"({moon.illumination:.0f}% illuminated)")
    elif moon.sets_at:
        console.print(f"  Moon sets at {moon.sets_at.strftime('%H:%M')} "
                      f"({moon.illumination:.0f}% illuminated)")
    else:
        console.print(f"  Moon: {moon.illumination:.0f}% illuminated")

    console.print(f"  Angular distance: {moon.min_angular_distance:.0f}° → "
                  f"{moon.severity.capitalize()} interference")

    if moon.severity in ("moderate", "severe"):
        console.print()
        console.print(f"  [dim]Consider adjusting session times to avoid moonlight[/]")

    console.print()


def _render_alternatives(ctx: CliContext, alternatives) -> None:
    """Render alternative windows table."""
    console = ctx.console

    console.print("[bold]\U0001F4C5 Alternative Windows:[/]")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Date", style="cyan")
    table.add_column("Window", style="white")
    table.add_column("Score", style="white", justify="right")
    table.add_column("Peak Alt", style="white", justify="right")
    table.add_column("Moon", style="white")

    for i, w in enumerate(alternatives):
        date = w.date.strftime("%a %d")
        window_str = f"{w.start.strftime('%H:%M')} - {w.end.strftime('%H:%M')}"
        score = f"{w.average_score:.0f}"
        peak = f"{w.peak_altitude:.0f}°"

        if w.moon_interference:
            moon = w.moon_interference
            if moon.severity == "none":
                moon_str = f"{moon.illumination:.0f}% (below)"
            else:
                moon_str = f"{moon.illumination:.0f}%"
                if moon.severity == "minor":
                    moon_str += " \u26A0"
                elif moon.severity in ("moderate", "severe"):
                    moon_str += " \u274C"
        else:
            moon_str = "-"

        # Mark best alternative
        if i == len(alternatives) - 1 and w.moon_interference and w.moon_interference.severity == "none":
            date += " \u2B50"

        table.add_row(date, window_str, score, peak, moon_str)

    console.print(table)
