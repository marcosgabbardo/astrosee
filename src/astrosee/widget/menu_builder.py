"""Menu construction logic for the widget."""

from datetime import datetime
from typing import Any

from astrosee.scoring.models import SeeingReport
from astrosee.widget.icons import (
    get_moon_icon,
    get_rating_text,
    get_weather_icon,
)


def build_conditions_menu(report: SeeingReport) -> list[tuple[str, Any]]:
    """Build menu items for current conditions.

    Args:
        report: Current seeing report

    Returns:
        List of (title, callback_or_none) tuples
    """
    items = []

    # Score header
    score = report.score.total_score
    rating = get_rating_text(score)
    items.append((f"\U0001F52D Score: {int(score)}/100 ({rating})", None))
    items.append((None, None))  # Separator

    # Weather conditions
    weather = report.weather
    temp_diff = abs(weather.temperature - weather.dew_point)
    items.append((f"\U0001F321\uFE0F Temp: {weather.temperature:.1f}\u00B0C (diff: {temp_diff:.1f}\u00B0)", None))
    items.append((f"\U0001F4A8 Wind: {weather.wind_speed_10m:.1f} m/s", None))

    cloud_icon = get_weather_icon(weather.cloud_cover)
    items.append((f"{cloud_icon} Clouds: {int(weather.cloud_cover)}%", None))
    items.append((f"\U0001F4A7 Humidity: {int(weather.humidity)}%", None))

    # Moon info
    moon_icon = get_moon_icon(
        report.astronomy.moon_illumination,
        report.astronomy.moon_altitude
    )
    moon_status = "below horizon" if report.astronomy.moon_altitude < 0 else f"alt: {report.astronomy.moon_altitude:.0f}\u00B0"
    items.append((f"{moon_icon} Moon: {int(report.astronomy.moon_illumination)}% ({moon_status})", None))

    return items


def build_component_scores_menu(report: SeeingReport) -> list[tuple[str, Any]]:
    """Build menu items for component scores.

    Args:
        report: Current seeing report

    Returns:
        List of (title, callback_or_none) tuples for submenu
    """
    items = []
    components = report.score.component_scores

    component_names = {
        "temperature_differential": "Temp Stability",
        "wind_stability": "Wind",
        "humidity": "Humidity",
        "cloud_cover": "Clouds",
        "jet_stream": "Jet Stream",
    }

    for key, score in components.items():
        name = component_names.get(key, key)
        bar = _score_bar(score, width=10)
        items.append((f"{name}: {bar} {score:.0f}", None))

    return items


def build_forecast_menu(
    best_nights: list[tuple[datetime, float, str]],
) -> list[tuple[str, Any]]:
    """Build menu items for forecast summary.

    Args:
        best_nights: List of (date, score, summary) tuples

    Returns:
        List of (title, callback_or_none) tuples
    """
    items = []

    if not best_nights:
        items.append(("No good nights in forecast", None))
        return items

    today = datetime.now().date()

    for night_date, score, summary in best_nights[:5]:  # Limit to 5
        date_label = _date_label(night_date.date(), today)
        icon = get_score_icon(score)
        items.append((f"{icon} {date_label}: {int(score)} - {summary}", None))

    return items


def build_best_window_menu(
    window_start: datetime | None,
    window_end: datetime | None,
    window_score: float | None,
) -> list[tuple[str, Any]]:
    """Build menu items for best observation window.

    Args:
        window_start: Start time of best window
        window_end: End time of best window
        window_score: Average score in window

    Returns:
        List of (title, callback_or_none) tuples
    """
    items = []

    if window_start and window_end and window_score:
        start_str = window_start.strftime("%H:%M")
        end_str = window_end.strftime("%H:%M")
        items.append((f"\U0001F4CA Tonight's Best: {start_str}-{end_str}", None))
        items.append((f"   Average score: {int(window_score)}", None))
    else:
        items.append(("\U0001F4CA No good window tonight", None))

    return items


def build_error_menu(error_message: str) -> list[tuple[str, Any]]:
    """Build menu items for error state.

    Args:
        error_message: Error message to display

    Returns:
        List of (title, callback_or_none) tuples
    """
    return [
        ("\u26A0\uFE0F Unable to fetch data", None),
        (f"   {error_message[:40]}", None),
        (None, None),  # Separator
        ("Click Refresh to retry", None),
    ]


def build_loading_menu() -> list[tuple[str, Any]]:
    """Build menu items for loading state.

    Returns:
        List of (title, callback_or_none) tuples
    """
    return [
        ("\u23F3 Loading...", None),
    ]


def _score_bar(score: float, width: int = 10) -> str:
    """Create a text progress bar for a score.

    Args:
        score: Score value (0-100)
        width: Bar width in characters

    Returns:
        Text progress bar string
    """
    filled = int(score / 100 * width)
    empty = width - filled
    return "\u2588" * filled + "\u2591" * empty


def _date_label(date: datetime.date, today: datetime.date) -> str:
    """Get human-readable date label.

    Args:
        date: Date to label
        today: Today's date for comparison

    Returns:
        Label like "Tonight", "Tomorrow", "Wed 15"
    """
    delta = (date - today).days

    if delta == 0:
        return "Tonight"
    elif delta == 1:
        return "Tomorrow"
    elif delta < 7:
        return date.strftime("%A")
    else:
        return date.strftime("%b %d")
