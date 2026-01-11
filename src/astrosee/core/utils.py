"""Common utilities."""

import math
from datetime import datetime, timezone


def validate_coordinates(lat: float, lon: float) -> tuple[float, float]:
    """Validate and normalize latitude/longitude.

    Args:
        lat: Latitude in degrees (-90 to 90)
        lon: Longitude in degrees (-180 to 180)

    Returns:
        Tuple of (latitude, longitude)

    Raises:
        ValueError: If coordinates are out of range
    """
    if not -90 <= lat <= 90:
        raise ValueError(f"Latitude must be between -90 and 90, got {lat}")
    if not -180 <= lon <= 180:
        raise ValueError(f"Longitude must be between -180 and 180, got {lon}")
    return (lat, lon)


def haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Calculate distance between two points on Earth in kilometers.

    Uses the Haversine formula for great-circle distance.

    Args:
        lat1, lon1: First point coordinates in degrees
        lat2, lon2: Second point coordinates in degrees

    Returns:
        Distance in kilometers
    """
    R = 6371  # Earth's radius in km

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def utc_now() -> datetime:
    """Get current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


def round_to_hour(dt: datetime) -> datetime:
    """Round datetime to the nearest hour (for cache keys)."""
    return dt.replace(minute=0, second=0, microsecond=0)


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value between min and max."""
    return max(min_val, min(max_val, value))


def linear_interpolate(
    value: float,
    in_min: float,
    in_max: float,
    out_min: float,
    out_max: float,
) -> float:
    """Linear interpolation from one range to another.

    Args:
        value: Input value
        in_min, in_max: Input range
        out_min, out_max: Output range

    Returns:
        Interpolated value in output range
    """
    if in_max == in_min:
        return out_min
    ratio = (value - in_min) / (in_max - in_min)
    return out_min + ratio * (out_max - out_min)
