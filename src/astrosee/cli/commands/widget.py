"""Widget command to launch the menu bar widget."""

import sys

import click


@click.command()
@click.option(
    "--interval",
    "-i",
    type=int,
    default=15,
    help="Update interval in minutes (default: 15)",
)
def widget(interval: int) -> None:
    """Launch the macOS menu bar widget.

    The widget displays the current seeing score in the menu bar
    and provides quick access to conditions and forecasts.

    Requires macOS and the rumps library.

    Examples:
        astrosee widget
        astrosee widget --interval 30
    """
    # Check if we're on macOS
    if sys.platform != "darwin":
        click.echo("Error: The menu bar widget is only available on macOS.", err=True)
        raise SystemExit(1)

    try:
        from astrosee.widget.app import AstroseeWidget
        from astrosee.storage.config import ConfigManager
    except ImportError as e:
        click.echo(
            f"Error: Failed to import widget components: {e}\n"
            "Make sure rumps is installed: pip install rumps",
            err=True,
        )
        raise SystemExit(1)

    # Check for location configuration
    config = ConfigManager()
    if not config.get_default_location():
        click.echo(
            "Warning: No location configured. "
            "Run 'astrosee config set' first to set your location.",
            err=True,
        )

    # Convert interval from minutes to seconds
    interval_seconds = interval * 60

    click.echo(f"Starting Astrosee widget (update every {interval} minutes)...")
    click.echo("The widget will appear in your menu bar.")
    click.echo("Press Ctrl+C to stop.")

    try:
        widget_app = AstroseeWidget(
            update_interval=interval_seconds,
            config=config,
        )
        widget_app.run()
    except KeyboardInterrupt:
        click.echo("\nWidget stopped.")
