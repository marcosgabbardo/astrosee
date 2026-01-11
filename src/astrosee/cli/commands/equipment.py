"""Equipment management commands."""

import click
from rich.table import Table

from astrosee.cli.context import CliContext
from astrosee.services.sessions import SessionManager


pass_context = click.make_pass_decorator(CliContext)


EQUIPMENT_TYPES = [
    "telescope",
    "eyepiece",
    "camera",
    "mount",
    "filter",
    "barlow",
    "focuser",
    "other",
]


@click.group()
def equipment() -> None:
    """Manage observation equipment.

    Track your astronomy equipment for session logging.

    Examples:
        astrosee equipment add "Celestron 8SE" --type telescope --aperture 203mm
        astrosee equipment list
        astrosee equipment remove celestron-8se
    """
    pass


@equipment.command()
@click.argument("name")
@click.option(
    "--type", "-t",
    "equipment_type",
    type=click.Choice(EQUIPMENT_TYPES),
    required=True,
    help="Equipment type",
)
@click.option(
    "--aperture",
    type=str,
    help="Aperture (e.g., '203mm', '8\"')",
)
@click.option(
    "--focal-length",
    type=str,
    help="Focal length (e.g., '2032mm', '32mm')",
)
@click.option(
    "--focal-ratio",
    type=str,
    help="Focal ratio (e.g., 'f/10', 'f/2.8')",
)
@click.option(
    "--notes", "-n",
    type=str,
    default="",
    help="Additional notes",
)
@pass_context
def add(
    ctx: CliContext,
    name: str,
    equipment_type: str,
    aperture: str | None,
    focal_length: str | None,
    focal_ratio: str | None,
    notes: str,
) -> None:
    """Add equipment to your collection.

    Examples:
        astrosee equipment add "Celestron 8SE" -t telescope --aperture 203mm --focal-length 2032mm
        astrosee equipment add "32mm Plossl" -t eyepiece --focal-length 32mm
        astrosee equipment add "ZWO ASI294MC" -t camera -n "Color planetary camera"
    """
    manager = SessionManager(ctx.config.config_dir)

    specs = {}
    if aperture:
        specs["aperture"] = aperture
    if focal_length:
        specs["focal_length"] = focal_length
    if focal_ratio:
        specs["focal_ratio"] = focal_ratio

    equipment = manager.add_equipment(
        name=name,
        equipment_type=equipment_type,
        specs=specs,
        notes=notes,
    )

    ctx.console.print()
    ctx.console.print(f"[green bold]Equipment added:[/] {equipment.name}")
    ctx.console.print(f"[dim]ID:[/] {equipment.id}")
    ctx.console.print(f"[dim]Type:[/] {equipment.equipment_type}")
    if equipment.specs:
        for key, value in equipment.specs.items():
            ctx.console.print(f"[dim]{key.replace('_', ' ').title()}:[/] {value}")


@equipment.command("list")
@click.option(
    "--type", "-t",
    "equipment_type",
    type=click.Choice(EQUIPMENT_TYPES),
    help="Filter by equipment type",
)
@pass_context
def list_equipment(ctx: CliContext, equipment_type: str | None) -> None:
    """List all equipment.

    Examples:
        astrosee equipment list
        astrosee equipment list -t eyepiece
    """
    manager = SessionManager(ctx.config.config_dir)

    equipment_list = manager.list_equipment(equipment_type)

    if not equipment_list:
        if equipment_type:
            ctx.console.print(f"[dim]No {equipment_type}s found.[/]")
        else:
            ctx.console.print("[dim]No equipment found. Add some with 'astrosee equipment add'.[/]")
        return

    table = Table(title="Equipment")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Type", style="green")
    table.add_column("Specs", style="dim")

    for eq in equipment_list:
        specs_str = ", ".join(f"{k}: {v}" for k, v in eq.specs.items()) if eq.specs else "-"
        table.add_row(eq.id, eq.name, eq.equipment_type, specs_str)

    ctx.console.print(table)


@equipment.command()
@click.argument("equipment_id")
@pass_context
def show(ctx: CliContext, equipment_id: str) -> None:
    """Show equipment details.

    Example:
        astrosee equipment show celestron-8se
    """
    manager = SessionManager(ctx.config.config_dir)

    eq = manager.get_equipment(equipment_id)

    if not eq:
        ctx.renderer.print_error(f"Equipment '{equipment_id}' not found.")
        raise SystemExit(1)

    ctx.console.print()
    ctx.console.print(f"[bold]{eq.name}[/]")
    ctx.console.print(f"[dim]ID:[/] {eq.id}")
    ctx.console.print(f"[dim]Type:[/] {eq.equipment_type}")

    if eq.specs:
        ctx.console.print()
        ctx.console.print("[bold]Specifications:[/]")
        for key, value in eq.specs.items():
            ctx.console.print(f"  {key.replace('_', ' ').title()}: {value}")

    if eq.notes:
        ctx.console.print()
        ctx.console.print(f"[bold]Notes:[/]")
        ctx.console.print(f"  {eq.notes}")


@equipment.command()
@click.argument("equipment_id")
@click.confirmation_option(prompt="Are you sure you want to remove this equipment?")
@pass_context
def remove(ctx: CliContext, equipment_id: str) -> None:
    """Remove equipment from collection.

    Example:
        astrosee equipment remove celestron-8se
    """
    manager = SessionManager(ctx.config.config_dir)

    if manager.remove_equipment(equipment_id):
        ctx.console.print(f"[green]Equipment '{equipment_id}' removed.[/]")
    else:
        ctx.renderer.print_error(f"Equipment '{equipment_id}' not found.")
        raise SystemExit(1)
