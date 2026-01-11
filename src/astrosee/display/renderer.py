"""Rich-based display renderer."""

from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from astrosee.display.formatters import (
    format_altitude,
    format_airmass,
    format_coordinates,
    format_date_short,
    format_duration,
    format_moon_phase,
    format_percentage,
    format_rating,
    format_score,
    format_score_bar,
    format_temperature,
    format_time_short,
    format_timestamp,
    format_wind,
    get_score_color,
)
from astrosee.scoring.models import (
    LocationComparison,
    ObservingWindow,
    SeeingForecast,
    SeeingReport,
)


class DisplayRenderer:
    """Renders seeing data to the terminal using Rich."""

    def __init__(self, console: Console | None = None):
        """Initialize renderer.

        Args:
            console: Rich console (creates one if not provided)
        """
        self.console = console or Console()

    def render_current_conditions(self, report: SeeingReport) -> None:
        """Render current seeing conditions.

        Args:
            report: SeeingReport to display
        """
        # Header
        header = Panel(
            f"[bold]ASTRONOMICAL SEEING FORECAST[/bold]\n"
            f"{report.location.name} ({format_coordinates(report.location.latitude, report.location.longitude)})\n"
            f"{format_timestamp(report.timestamp)}",
            style="blue",
        )
        self.console.print(header)

        # Overall score
        score = report.score
        score_color = get_score_color(score.total_score)
        score_panel = Panel(
            f"[bold]{format_score(score.total_score)}[/bold]  "
            f"{format_score_bar(score.total_score)}  "
            f"[{score_color}]{format_rating(score.total_score)}[/{score_color}]",
            title="Overall Score",
            border_style=score_color,
        )
        self.console.print(score_panel)

        # Component breakdown
        self._render_component_breakdown(score.component_scores)

        # Weather details
        self._render_weather_details(report)

        # Moon info
        self._render_moon_info(report)

        # Target info if available
        if report.target:
            self._render_target_info(report)

        # Recommendations
        self._render_recommendations(report)

    def _render_component_breakdown(self, components: dict[str, float]) -> None:
        """Render component score breakdown."""
        table = Table(title="Conditions Breakdown", show_header=False, box=None)
        table.add_column("Component", style="cyan")
        table.add_column("Score", justify="right")
        table.add_column("Bar", width=12)

        component_names = {
            "temperature_differential": "Temperature Stability",
            "wind_stability": "Wind Conditions",
            "humidity": "Humidity",
            "cloud_cover": "Cloud Cover",
            "jet_stream": "Jet Stream",
        }

        for key, value in components.items():
            name = component_names.get(key, key.replace("_", " ").title())
            table.add_row(
                f"├─ {name}",
                format_score(value),
                format_score_bar(value),
            )

        self.console.print(table)
        self.console.print()

    def _render_weather_details(self, report: SeeingReport) -> None:
        """Render weather details."""
        w = report.weather

        table = Table(title="Atmospheric Details", show_header=False, box=None)
        table.add_column("Label", style="dim")
        table.add_column("Value")

        table.add_row(
            "├─ Temp differential:",
            f"{w.temperature_differential:.1f}°C "
            f"({'stable' if w.temperature_differential > 5 else 'unstable'})",
        )

        if w.wind_shear is not None:
            table.add_row(
                "├─ Wind shear:",
                f"{w.wind_shear:.1f} m/s ({'low' if w.wind_shear < 5 else 'moderate' if w.wind_shear < 10 else 'high'})",
            )

        table.add_row(
            "├─ Surface wind:",
            format_wind(w.wind_speed_10m, w.wind_direction),
        )

        table.add_row("├─ Cloud cover:", format_percentage(w.cloud_cover))
        table.add_row("├─ Humidity:", format_percentage(w.humidity))
        table.add_row("├─ Pressure:", f"{w.pressure:.0f} hPa")

        if w.jet_stream_speed is not None:
            jet_quality = "calm" if w.jet_stream_speed < 30 else "moderate" if w.jet_stream_speed < 50 else "strong"
            table.add_row(
                "└─ Jet stream:",
                f"{w.jet_stream_speed:.0f} m/s ({jet_quality})",
            )

        self.console.print(table)
        self.console.print()

    def _render_moon_info(self, report: SeeingReport) -> None:
        """Render moon information."""
        astro = report.astronomy
        moon_str = format_moon_phase(astro.moon_illumination, astro.moon_phase)

        if astro.moon_altitude > 0:
            moon_str += f", altitude: {astro.moon_altitude:.0f}°"
        else:
            moon_str += " (below horizon)"

        self.console.print(f"Moon: {moon_str}")
        self.console.print()

    def _render_target_info(self, report: SeeingReport) -> None:
        """Render target object information."""
        target = report.target
        pos = report.target_position

        if not target or not pos:
            return

        panel_content = []
        panel_content.append(f"[bold]{target.name}[/bold] ({target.designation})")

        if pos.is_visible:
            panel_content.append(f"Altitude: {format_altitude(pos.altitude)}")
            panel_content.append(f"Azimuth: {pos.azimuth:.0f}°")
            panel_content.append(f"Airmass: {format_airmass(pos.airmass)}")
        else:
            panel_content.append("[red]Currently below horizon[/red]")

        if target.magnitude is not None:
            panel_content.append(f"Magnitude: {target.magnitude:.1f}")

        panel = Panel(
            "\n".join(panel_content),
            title=f"Target: {target.name}",
            border_style="cyan",
        )
        self.console.print(panel)

    def _render_recommendations(self, report: SeeingReport) -> None:
        """Render observation recommendations."""
        score = report.score

        # Overall recommendation
        rec_text = score.recommendation

        # Target type recommendations
        from astrosee.scoring.engine import ScoringEngine
        engine = ScoringEngine()
        targets = engine.get_best_targets(score, report.weather)

        target_lines = []
        for target_type, quality in targets.items():
            color = "green" if quality in ["Excellent", "Good"] else "yellow" if quality == "Fair" else "red"
            target_lines.append(f"  {target_type.replace('_', ' ').title()}: [{color}]{quality}[/{color}]")

        panel = Panel(
            f"{rec_text}\n\n" + "\n".join(target_lines),
            title="Recommendation",
            border_style="green" if score.total_score >= 60 else "yellow" if score.total_score >= 40 else "red",
        )
        self.console.print(panel)

    def render_forecast_table(
        self,
        forecasts: list[SeeingForecast],
        title: str = "Forecast",
    ) -> None:
        """Render forecast as a table.

        Args:
            forecasts: List of forecast entries
            title: Table title
        """
        table = Table(title=title)
        table.add_column("Time", style="cyan")
        table.add_column("Score", justify="right")
        table.add_column("Quality")
        table.add_column("Clouds", justify="right")
        table.add_column("Wind", justify="right")
        table.add_column("Night", justify="center")

        for f in forecasts:
            night_str = "🌙" if f.is_night else "☀️"
            table.add_row(
                format_timestamp(f.timestamp),
                format_score(f.score.total_score),
                f"[{get_score_color(f.score.total_score)}]{format_rating(f.score.total_score)}[/{get_score_color(f.score.total_score)}]",
                format_percentage(f.weather.cloud_cover),
                format_wind(f.weather.wind_speed_10m),
                night_str,
            )

        self.console.print(table)

    def render_daily_forecast(
        self,
        daily_data: list[tuple[datetime, float, str]],
    ) -> None:
        """Render daily forecast summary.

        Args:
            daily_data: List of (date, avg_score, summary) tuples
        """
        table = Table(title="7-Day Forecast")
        table.add_column("Date", style="cyan")
        table.add_column("Score", justify="right")
        table.add_column("Summary")

        for date, score, summary in daily_data:
            table.add_row(
                format_date_short(date),
                format_score(score),
                summary,
            )

        self.console.print(table)

        if daily_data:
            best = max(daily_data, key=lambda x: x[1])
            self.console.print(
                f"\n⭐ Best night: [bold]{format_date_short(best[0])}[/bold] "
                f"(score: {format_score(best[1])})"
            )

    def render_best_window(self, window: ObservingWindow | None) -> None:
        """Render best observation window.

        Args:
            window: Observation window or None
        """
        if window is None:
            self.console.print(
                Panel(
                    "[yellow]No suitable observation window found in the forecast period.[/yellow]",
                    title="Best Window",
                    border_style="yellow",
                )
            )
            return

        content = [
            f"[bold]Start:[/bold] {format_timestamp(window.start)}",
            f"[bold]End:[/bold] {format_timestamp(window.end)}",
            f"[bold]Duration:[/bold] {format_duration(window.duration_hours)}",
            "",
            f"Average score: {format_score(window.average_score)}",
            f"Peak score: {format_score(window.peak_score)} at {format_time_short(window.peak_time)}",
        ]

        panel = Panel(
            "\n".join(content),
            title="🎯 Best Observation Window",
            border_style="green",
        )
        self.console.print(panel)

    def render_location_comparison(self, comparison: LocationComparison) -> None:
        """Render location comparison.

        Args:
            comparison: Location comparison data
        """
        table = Table(title="Location Comparison")
        table.add_column("Location", style="cyan")
        table.add_column("Score", justify="right")
        table.add_column("Quality")
        table.add_column("Clouds", justify="right")
        table.add_column("Wind", justify="right")

        ranked = comparison.ranked()
        for i, (loc, report) in enumerate(ranked):
            prefix = "🏆 " if i == 0 else "   "
            table.add_row(
                f"{prefix}{loc.name}",
                format_score(report.score.total_score),
                format_rating(report.score.total_score),
                format_percentage(report.weather.cloud_cover),
                format_wind(report.weather.wind_speed_10m),
            )

        self.console.print(table)

        best_loc, best_report = comparison.best_location
        self.console.print(
            f"\n✨ Best location: [bold]{best_loc.name}[/bold] "
            f"with score {format_score(best_report.score.total_score)}"
        )

    def render_target_visibility(
        self,
        target_name: str,
        visibility_data: list[dict],
    ) -> None:
        """Render target visibility over time.

        Args:
            target_name: Target object name
            visibility_data: Visibility data from forecast service
        """
        table = Table(title=f"Target: {target_name}")
        table.add_column("Time", style="cyan")
        table.add_column("Alt", justify="right")
        table.add_column("Airmass", justify="right")
        table.add_column("Score", justify="right")
        table.add_column("Night", justify="center")

        for entry in visibility_data:
            if not entry["is_visible"]:
                continue

            night_str = "🌙" if entry["is_night"] else "☀️"
            table.add_row(
                format_time_short(entry["time"]),
                format_altitude(entry["altitude"]),
                f"{entry['airmass']:.2f}",
                format_score(entry["score"]),
                night_str,
            )

        self.console.print(table)

        # Find optimal time
        visible = [e for e in visibility_data if e["is_visible"] and e["is_night"]]
        if visible:
            best = min(visible, key=lambda e: e["airmass"])
            self.console.print(
                f"\n🎯 Optimal viewing: [bold]{format_time_short(best['time'])}[/bold] "
                f"(altitude: {best['altitude']:.0f}°, airmass: {best['airmass']:.2f})"
            )

    def print_success(self, message: str) -> None:
        """Print success message."""
        self.console.print(f"[green]✓[/green] {message}")

    def print_warning(self, message: str) -> None:
        """Print warning message."""
        self.console.print(f"[yellow]⚠[/yellow] {message}")

    def print_error(self, message: str) -> None:
        """Print error message."""
        self.console.print(f"[red]✗[/red] {message}")
