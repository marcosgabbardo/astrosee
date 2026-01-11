"""Formatting utilities for display."""

from datetime import datetime


def format_score(score: float) -> str:
    """Format score with color markup for Rich.

    Args:
        score: Score value 0-100

    Returns:
        Rich-formatted score string
    """
    color = get_score_color(score)
    return f"[{color}]{score:.0f}[/{color}]"


def get_score_color(score: float) -> str:
    """Get Rich color for score value.

    Args:
        score: Score value 0-100

    Returns:
        Rich color name
    """
    if score >= 85:
        return "bright_green"
    elif score >= 70:
        return "green"
    elif score >= 55:
        return "yellow"
    elif score >= 40:
        return "orange1"
    elif score >= 25:
        return "red"
    else:
        return "bright_red"


def format_score_bar(score: float, width: int = 10) -> str:
    """Format score as a progress bar.

    Args:
        score: Score value 0-100
        width: Bar width in characters

    Returns:
        Unicode progress bar string
    """
    filled = int(score / 100 * width)
    empty = width - filled
    color = get_score_color(score)

    bar = "█" * filled + "░" * empty
    return f"[{color}]{bar}[/{color}]"


def format_rating(score: float) -> str:
    """Get rating text for score.

    Args:
        score: Score value 0-100

    Returns:
        Rating string
    """
    if score >= 85:
        return "EXCELLENT"
    elif score >= 70:
        return "VERY GOOD"
    elif score >= 55:
        return "GOOD"
    elif score >= 40:
        return "FAIR"
    elif score >= 25:
        return "POOR"
    else:
        return "BAD"


def format_timestamp(dt: datetime, include_date: bool = True) -> str:
    """Format datetime for display.

    Args:
        dt: Datetime to format
        include_date: Whether to include date

    Returns:
        Formatted string
    """
    if include_date:
        return dt.strftime("%Y-%m-%d %H:%M")
    return dt.strftime("%H:%M")


def format_time_short(dt: datetime) -> str:
    """Format time in short form (HH:MM).

    Args:
        dt: Datetime to format

    Returns:
        Formatted string
    """
    return dt.strftime("%H:%M")


def format_date_short(dt: datetime) -> str:
    """Format date in short form (Mon 15th).

    Args:
        dt: Datetime to format

    Returns:
        Formatted string
    """
    day = dt.day
    suffix = "th" if 11 <= day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return dt.strftime(f"%a {day}{suffix}")


def format_coordinates(lat: float, lon: float) -> str:
    """Format coordinates for display.

    Args:
        lat: Latitude
        lon: Longitude

    Returns:
        Formatted string like "29.18°S, 49.64°W"
    """
    lat_dir = "N" if lat >= 0 else "S"
    lon_dir = "E" if lon >= 0 else "W"
    return f"{abs(lat):.2f}°{lat_dir}, {abs(lon):.2f}°{lon_dir}"


def format_wind(speed: float, direction: float | None = None) -> str:
    """Format wind speed and direction.

    Args:
        speed: Wind speed in m/s
        direction: Wind direction in degrees (optional)

    Returns:
        Formatted string
    """
    speed_kmh = speed * 3.6
    if direction is not None:
        dir_str = get_wind_direction_name(direction)
        return f"{speed_kmh:.1f} km/h {dir_str}"
    return f"{speed_kmh:.1f} km/h"


def get_wind_direction_name(degrees: float) -> str:
    """Get cardinal direction from degrees.

    Args:
        degrees: Wind direction in degrees (0=N, 90=E)

    Returns:
        Cardinal direction string (N, NE, E, etc.)
    """
    directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                  "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    idx = round(degrees / 22.5) % 16
    return directions[idx]


def format_temperature(temp: float) -> str:
    """Format temperature.

    Args:
        temp: Temperature in Celsius

    Returns:
        Formatted string
    """
    return f"{temp:.1f}°C"


def format_percentage(value: float) -> str:
    """Format percentage value.

    Args:
        value: Value 0-100

    Returns:
        Formatted string
    """
    return f"{value:.0f}%"


def format_airmass(airmass: float) -> str:
    """Format airmass value with quality indicator.

    Args:
        airmass: Airmass value

    Returns:
        Formatted string with quality
    """
    if airmass <= 1.2:
        quality = "[bright_green]excellent[/bright_green]"
    elif airmass <= 1.5:
        quality = "[green]good[/green]"
    elif airmass <= 2.0:
        quality = "[yellow]fair[/yellow]"
    elif airmass <= 3.0:
        quality = "[orange1]poor[/orange1]"
    else:
        quality = "[red]very poor[/red]"

    return f"{airmass:.2f} ({quality})"


def format_altitude(altitude: float) -> str:
    """Format altitude with quality indicator.

    Args:
        altitude: Altitude in degrees

    Returns:
        Formatted string
    """
    if altitude > 60:
        return f"[bright_green]{altitude:.0f}°[/bright_green]"
    elif altitude > 30:
        return f"[green]{altitude:.0f}°[/green]"
    elif altitude > 15:
        return f"[yellow]{altitude:.0f}°[/yellow]"
    elif altitude > 0:
        return f"[orange1]{altitude:.0f}°[/orange1]"
    else:
        return f"[red]{altitude:.0f}° (below horizon)[/red]"


def format_moon_phase(illumination: float, phase_name: str) -> str:
    """Format moon phase with emoji.

    Args:
        illumination: Moon illumination percentage
        phase_name: Phase name

    Returns:
        Formatted string with emoji
    """
    # Select appropriate moon emoji
    if illumination < 5:
        emoji = "🌑"
    elif illumination < 25:
        emoji = "🌒"
    elif illumination < 50:
        emoji = "🌓"
    elif illumination < 75:
        emoji = "🌔"
    elif illumination < 95:
        emoji = "🌕"
    else:
        emoji = "🌕"

    return f"{emoji} {phase_name} ({illumination:.0f}% illuminated)"


def format_duration(hours: float) -> str:
    """Format duration in hours.

    Args:
        hours: Duration in hours

    Returns:
        Formatted string like "3h 30m"
    """
    h = int(hours)
    m = int((hours - h) * 60)
    if m == 0:
        return f"{h}h"
    return f"{h}h {m}m"
