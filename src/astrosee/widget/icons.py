"""Score-to-icon mapping for menu bar widget."""


def get_score_icon(score: float) -> str:
    """Get emoji icon based on seeing score.

    Args:
        score: Seeing score (0-100)

    Returns:
        Emoji character representing the score quality
    """
    if score >= 85:
        return "\u2B50"  # Star (Excellent)
    elif score >= 70:
        return "\U0001F319"  # Crescent Moon (Good)
    elif score >= 55:
        return "\u2601\uFE0F"  # Cloud (Fair)
    elif score >= 25:
        return "\U0001F32B\uFE0F"  # Fog (Poor)
    else:
        return "\u274C"  # X (Bad)


def get_score_title(score: float) -> str:
    """Get menu bar title string with icon and score.

    Args:
        score: Seeing score (0-100)

    Returns:
        Title string like "78" or "--"
    """
    if score < 0:
        return "--"
    return str(int(round(score)))


def get_rating_text(score: float) -> str:
    """Get rating text for score.

    Args:
        score: Seeing score (0-100)

    Returns:
        Rating text (Excellent, Good, Fair, Poor, Bad)
    """
    if score >= 85:
        return "Excellent"
    elif score >= 70:
        return "Good"
    elif score >= 55:
        return "Fair"
    elif score >= 25:
        return "Poor"
    else:
        return "Bad"


def get_activity_icon(activity: str) -> str:
    """Get icon for activity type.

    Args:
        activity: Activity type string

    Returns:
        Emoji for activity
    """
    icons = {
        "visual": "\U0001F52D",  # Telescope
        "deep_sky": "\U0001F30C",  # Milky Way
        "planetary": "\U0001FA90",  # Ringed Planet
        "moon": "\U0001F315",  # Full Moon
        "imaging": "\U0001F4F7",  # Camera
    }
    return icons.get(activity, "\u2B50")


def get_weather_icon(cloud_cover: float) -> str:
    """Get weather icon based on cloud cover.

    Args:
        cloud_cover: Cloud cover percentage (0-100)

    Returns:
        Weather emoji
    """
    if cloud_cover < 10:
        return "\u2728"  # Sparkles (clear)
    elif cloud_cover < 30:
        return "\U0001F324\uFE0F"  # Sun behind small cloud
    elif cloud_cover < 60:
        return "\u26C5"  # Sun behind cloud
    elif cloud_cover < 85:
        return "\U0001F325\uFE0F"  # Sun behind large cloud
    else:
        return "\u2601\uFE0F"  # Cloud


def get_moon_icon(illumination: float, altitude: float) -> str:
    """Get moon icon based on illumination and position.

    Args:
        illumination: Moon illumination percentage (0-100)
        altitude: Moon altitude in degrees

    Returns:
        Moon phase emoji
    """
    if altitude < 0:
        return "\U0001F311"  # New moon (below horizon indicator)

    if illumination < 5:
        return "\U0001F311"  # New moon
    elif illumination < 25:
        return "\U0001F312"  # Waxing crescent
    elif illumination < 45:
        return "\U0001F313"  # First quarter
    elif illumination < 55:
        return "\U0001F314"  # Waxing gibbous
    elif illumination < 75:
        return "\U0001F315"  # Full moon
    elif illumination < 90:
        return "\U0001F316"  # Waning gibbous
    else:
        return "\U0001F317"  # Last quarter
