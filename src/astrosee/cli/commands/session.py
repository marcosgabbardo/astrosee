"""Session logging commands."""

import asyncio
from datetime import datetime
from pathlib import Path

import click
from rich.table import Table

from astrosee.cli.context import CliContext
from astrosee.core.exceptions import AstroseeError
from astrosee.services.sessions import SessionError, SessionExporter, SessionManager


pass_context = click.make_pass_decorator(CliContext)


@click.group()
def session() -> None:
    """Manage observation sessions.

    Track your observation sessions, log targets, and export data.

    Examples:
        astrosee session start
        astrosee session log "M31" --rating 4
        astrosee session note "Seeing improved"
        astrosee session end
        astrosee session list
    """
    pass


@session.command()
@pass_context
def start(ctx: CliContext) -> None:
    """Start a new observation session.

    Records current conditions and location for the session.
    You must have a location configured before starting a session.

    Example:
        astrosee session start
    """
    asyncio.run(_start_async(ctx))


async def _start_async(ctx: CliContext) -> None:
    """Async implementation of session start."""
    try:
        # Get location
        loc = ctx.config.get_default_location()
        if not loc:
            ctx.renderer.print_error(
                "No default location set. Use 'astrosee config set' first."
            )
            raise SystemExit(1)

        manager = SessionManager(ctx.config.config_dir)

        # Check for active session
        active = manager.get_active_session()
        if active:
            ctx.renderer.print_error(
                f"Session {active.id} is already active. End it first with 'astrosee session end'."
            )
            raise SystemExit(1)

        # Get current conditions
        seeing_service = ctx.get_seeing_service()

        with ctx.console.status("Fetching conditions..."):
            report = await seeing_service.get_current_conditions(location=loc)

        # Start session
        session = manager.start_session(loc, report)

        ctx.console.print()
        ctx.console.print(f"[green bold]Session started:[/] {session.id}")
        ctx.console.print(f"[dim]Location:[/] {loc.name}")
        ctx.console.print(
            f"[dim]Conditions:[/] Score {int(session.initial_conditions.total_score)}/100 "
            f"({session.initial_conditions.rating})"
        )
        ctx.console.print()
        ctx.console.print("[dim]Use 'astrosee session log' to record observations.[/]")

    except SessionError as e:
        ctx.renderer.print_error(str(e))
        raise SystemExit(1)
    except AstroseeError as e:
        ctx.renderer.print_error(str(e))
        raise SystemExit(1)
    finally:
        await ctx.cleanup()


@session.command()
@click.argument("target")
@click.option(
    "--rating", "-r",
    type=click.IntRange(1, 5),
    required=True,
    help="Quality rating from 1 (poor) to 5 (excellent)",
)
@click.option(
    "--notes", "-n",
    type=str,
    default="",
    help="Observation notes",
)
@pass_context
def log(ctx: CliContext, target: str, rating: int, notes: str) -> None:
    """Log a target observation.

    Records a target observation with a quality rating.

    Examples:
        astrosee session log "M31" --rating 4
        astrosee session log "Jupiter" -r 5 -n "Great detail in bands"
    """
    manager = SessionManager(ctx.config.config_dir)

    try:
        active = manager.get_active_session()
        if not active:
            ctx.renderer.print_error(
                "No active session. Start one with 'astrosee session start'."
            )
            raise SystemExit(1)

        observation = manager.log_observation(
            target_name=target,
            quality_rating=rating,
            notes=notes,
        )

        rating_stars = "\u2605" * rating + "\u2606" * (5 - rating)
        ctx.console.print()
        ctx.console.print(f"[green]Logged:[/] {target} {rating_stars}")
        if notes:
            ctx.console.print(f"[dim]Notes:[/] {notes}")
        ctx.console.print(
            f"[dim]Session has {active.target_count + 1} observation(s)[/]"
        )

    except SessionError as e:
        ctx.renderer.print_error(str(e))
        raise SystemExit(1)


@session.command()
@click.argument("text")
@pass_context
def note(ctx: CliContext, text: str) -> None:
    """Add a note to the current session.

    Example:
        astrosee session note "Seeing improved after midnight"
    """
    manager = SessionManager(ctx.config.config_dir)

    try:
        manager.add_note(text)
        ctx.console.print("[green]Note added to session.[/]")

    except SessionError as e:
        ctx.renderer.print_error(str(e))
        raise SystemExit(1)


@session.command()
@pass_context
def end(ctx: CliContext) -> None:
    """End the current observation session.

    Example:
        astrosee session end
    """
    manager = SessionManager(ctx.config.config_dir)

    try:
        session = manager.end_session()

        duration = session.duration_hours or 0
        hours = int(duration)
        minutes = int((duration - hours) * 60)

        ctx.console.print()
        ctx.console.print(f"[green bold]Session ended:[/] {session.id}")
        ctx.console.print(f"[dim]Duration:[/] {hours}h {minutes}m")
        ctx.console.print(f"[dim]Targets observed:[/] {session.target_count}")

        if session.targets_observed:
            ctx.console.print()
            ctx.console.print("[dim]Observations:[/]")
            for obs in session.targets_observed:
                stars = "\u2605" * obs.quality_rating + "\u2606" * (5 - obs.quality_rating)
                ctx.console.print(f"  - {obs.target_name} {stars}")

    except SessionError as e:
        ctx.renderer.print_error(str(e))
        raise SystemExit(1)


@session.command("list")
@click.option(
    "--limit", "-n",
    type=int,
    default=10,
    help="Maximum number of sessions to show",
)
@pass_context
def list_sessions(ctx: CliContext, limit: int) -> None:
    """List observation sessions.

    Example:
        astrosee session list
        astrosee session list -n 20
    """
    manager = SessionManager(ctx.config.config_dir)

    sessions = manager.list_sessions(limit=limit)

    if not sessions:
        ctx.console.print("[dim]No sessions found.[/]")
        return

    table = Table(title="Observation Sessions")
    table.add_column("Date", style="cyan")
    table.add_column("Location", style="white")
    table.add_column("Duration", style="white")
    table.add_column("Score", style="white")
    table.add_column("Targets", style="green")
    table.add_column("Status", style="white")

    for s in sessions:
        date = s.start_time.strftime("%Y-%m-%d %H:%M")

        if s.duration_hours:
            hours = int(s.duration_hours)
            minutes = int((s.duration_hours - hours) * 60)
            duration = f"{hours}h {minutes}m"
        else:
            duration = "--"

        score = f"{int(s.initial_conditions.total_score)}/100"

        targets = ", ".join(t.target_name for t in s.targets_observed[:3])
        if s.target_count > 3:
            targets += f" +{s.target_count - 3}"
        if not targets:
            targets = "-"

        status = "[yellow]Active[/]" if s.is_active else "[green]Completed[/]"

        table.add_row(date, s.location.name, duration, score, targets, status)

    ctx.console.print(table)


@session.command()
@click.argument("session_id")
@pass_context
def show(ctx: CliContext, session_id: str) -> None:
    """Show details of a specific session.

    Example:
        astrosee session show 2024-01-15T21-30-00
    """
    manager = SessionManager(ctx.config.config_dir)

    session = manager.get_session(session_id)

    if not session:
        ctx.renderer.print_error(f"Session '{session_id}' not found.")
        raise SystemExit(1)

    ctx.console.print()
    ctx.console.print(f"[bold]Session:[/] {session.id}")
    ctx.console.print(f"[dim]Status:[/] {'Active' if session.is_active else 'Completed'}")
    ctx.console.print()

    ctx.console.print(f"[bold]Location:[/] {session.location.name}")
    ctx.console.print(
        f"[dim]Coordinates:[/] {session.location.latitude:.4f}, {session.location.longitude:.4f}"
    )
    ctx.console.print()

    ctx.console.print(f"[bold]Time:[/]")
    ctx.console.print(f"  Start: {session.start_time.strftime('%Y-%m-%d %H:%M')}")
    if session.end_time:
        ctx.console.print(f"  End:   {session.end_time.strftime('%Y-%m-%d %H:%M')}")
        ctx.console.print(f"  Duration: {session.duration_hours:.1f} hours")
    ctx.console.print()

    ctx.console.print(f"[bold]Initial Conditions:[/]")
    ctx.console.print(
        f"  Score: {int(session.initial_conditions.total_score)}/100 "
        f"({session.initial_conditions.rating})"
    )
    ctx.console.print()

    if session.equipment_used:
        ctx.console.print(f"[bold]Equipment:[/]")
        for eq_id in session.equipment_used:
            ctx.console.print(f"  - {eq_id}")
        ctx.console.print()

    if session.targets_observed:
        ctx.console.print(f"[bold]Observations ({session.target_count}):[/]")
        for obs in session.targets_observed:
            stars = "\u2605" * obs.quality_rating + "\u2606" * (5 - obs.quality_rating)
            ctx.console.print(f"  {obs.observed_at.strftime('%H:%M')} - {obs.target_name} {stars}")
            if obs.notes:
                ctx.console.print(f"         [dim]{obs.notes}[/]")
        ctx.console.print()

    if session.notes:
        ctx.console.print(f"[bold]Notes:[/]")
        ctx.console.print(f"  {session.notes}")


@session.command()
@click.option(
    "--format", "-f",
    type=click.Choice(["json", "csv"]),
    default="json",
    help="Export format",
)
@click.option(
    "--output", "-o",
    type=click.Path(),
    help="Output file path (prints to stdout if not specified)",
)
@click.option(
    "--observations",
    is_flag=True,
    help="Export individual observations (CSV only)",
)
@pass_context
def export(ctx: CliContext, format: str, output: str | None, observations: bool) -> None:
    """Export sessions to JSON or CSV.

    Examples:
        astrosee session export
        astrosee session export -f csv -o sessions.csv
        astrosee session export -f csv --observations -o observations.csv
    """
    manager = SessionManager(ctx.config.config_dir)

    sessions = manager.list_sessions()

    if not sessions:
        ctx.console.print("[dim]No sessions to export.[/]")
        return

    exporter = SessionExporter(sessions)

    if format == "json":
        content = exporter.to_json()
    else:
        if observations:
            content = exporter.to_observations_csv()
        else:
            content = exporter.to_csv()

    if output:
        path = Path(output)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        ctx.console.print(f"[green]Exported {len(sessions)} session(s) to {path}[/]")
    else:
        ctx.console.print(content)


@session.command()
@click.argument("session_id")
@click.confirmation_option(prompt="Are you sure you want to delete this session?")
@pass_context
def delete(ctx: CliContext, session_id: str) -> None:
    """Delete a session.

    Example:
        astrosee session delete 2024-01-15T21-30-00
    """
    manager = SessionManager(ctx.config.config_dir)

    if manager.delete_session(session_id):
        ctx.console.print(f"[green]Session {session_id} deleted.[/]")
    else:
        ctx.renderer.print_error(f"Session '{session_id}' not found.")
        raise SystemExit(1)
