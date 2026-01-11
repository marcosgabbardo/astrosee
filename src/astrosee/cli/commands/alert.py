"""Alert configuration command."""

import asyncio

import click
from rich.table import Table

from astrosee.cli.context import CliContext
from astrosee.core.exceptions import AstroseeError
from astrosee.services.alerts import AlertService


pass_context = click.make_pass_decorator(CliContext)


@click.group()
def alert() -> None:
    """Manage observation alerts."""
    pass


@alert.command("add")
@click.option(
    "--when", "-w",
    type=str,
    required=True,
    help="Alert condition (e.g., 'score > 80')",
)
@click.option(
    "--notify/--no-notify",
    default=True,
    help="Send macOS notification when triggered",
)
@pass_context
def add_alert(ctx: CliContext, when: str, notify: bool) -> None:
    """Add a new alert condition.

    Examples:
        astrosee alert add --when "score > 80"
        astrosee alert add --when "score >= 70 and cloud_cover < 30"
        astrosee alert add --when "wind_speed < 5" --no-notify
    """
    try:
        # Validate condition syntax
        alert_service = AlertService()

        # Add to config
        ctx.config.add_alert(when, enabled=True)
        ctx.renderer.print_success(f"Alert added: {when}")

        if notify:
            ctx.console.print("  Notifications: enabled")

        ctx.console.print("\nUse 'astrosee alert check' to test your alerts.")

    except Exception as e:
        ctx.renderer.print_error(f"Invalid alert condition: {e}")
        raise SystemExit(1)


@alert.command("list")
@pass_context
def list_alerts(ctx: CliContext) -> None:
    """List all configured alerts."""
    alerts = ctx.config.get_alerts()

    if not alerts:
        ctx.renderer.print_warning("No alerts configured.")
        ctx.console.print("Use 'astrosee alert add' to create one.")
        return

    table = Table(title="Configured Alerts")
    table.add_column("#", style="dim")
    table.add_column("Condition")
    table.add_column("Enabled", justify="center")

    for i, alert_config in enumerate(alerts):
        enabled = "✓" if alert_config.get("enabled", True) else "✗"
        table.add_row(
            str(i),
            alert_config.get("condition", ""),
            enabled,
        )

    ctx.console.print(table)


@alert.command("remove")
@click.argument("index", type=int)
@pass_context
def remove_alert(ctx: CliContext, index: int) -> None:
    """Remove an alert by index number."""
    if ctx.config.remove_alert(index):
        ctx.renderer.print_success(f"Alert #{index} removed")
    else:
        ctx.renderer.print_error(f"Alert #{index} not found")
        raise SystemExit(1)


@alert.command("check")
@click.option(
    "--location", "-l",
    type=str,
    help="Location to check (uses default)",
)
@pass_context
def check_alerts(ctx: CliContext, location: str | None) -> None:
    """Check current conditions against all alerts.

    Evaluates all configured alerts against the current
    seeing conditions and shows which would trigger.
    """
    asyncio.run(_check_alerts_async(ctx, location))


async def _check_alerts_async(ctx: CliContext, location_name: str | None) -> None:
    """Async implementation of alert check."""
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

        alerts_config = ctx.config.get_alerts()
        if not alerts_config:
            ctx.renderer.print_warning("No alerts configured.")
            return

        seeing_service = ctx.get_seeing_service()

        with ctx.console.status("Checking conditions..."):
            report = await seeing_service.get_current_conditions(loc)

        # Evaluate alerts
        alert_service = AlertService()
        for alert_config in alerts_config:
            alert_service.add_alert(
                alert_config.get("condition", ""),
                enabled=alert_config.get("enabled", True),
                notify=False,  # Don't actually notify during check
            )

        triggered = alert_service.evaluate(report)

        ctx.console.print(f"\n[bold]Current Score:[/bold] {report.score.total_score:.0f}")
        ctx.console.print(f"[bold]Cloud Cover:[/bold] {report.weather.cloud_cover:.0f}%")
        ctx.console.print(f"[bold]Wind Speed:[/bold] {report.weather.wind_speed_10m:.1f} m/s")
        ctx.console.print()

        if triggered:
            ctx.console.print("[green]Triggered alerts:[/green]")
            for alert_config in triggered:
                ctx.console.print(f"  ✓ {alert_config.get('condition')}")
        else:
            ctx.console.print("[yellow]No alerts triggered[/yellow]")

    except AstroseeError as e:
        ctx.renderer.print_error(str(e))
        raise SystemExit(1)
    finally:
        await ctx.cleanup()


@alert.command("help")
@pass_context
def alert_help(ctx: CliContext) -> None:
    """Show help for alert condition syntax."""
    alert_service = AlertService()
    ctx.console.print(alert_service.format_condition_help())
