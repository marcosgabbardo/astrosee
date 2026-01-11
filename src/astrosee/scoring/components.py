"""Individual scoring component functions.

Each function calculates a score from 0-100 for a specific atmospheric factor.
Higher scores indicate better seeing conditions.
"""

from astrosee.core.utils import clamp, linear_interpolate
from astrosee.weather.models import WeatherData


def calculate_temperature_differential_score(weather: WeatherData) -> float:
    """Calculate score based on temperature-dewpoint differential.

    Higher differential = drier air = better seeing.
    Differential < 2°C = condensation risk, very poor.
    Differential > 10°C = excellent, dry air.

    Args:
        weather: Weather data

    Returns:
        Score 0-100
    """
    diff = weather.temperature_differential

    if diff >= 15:
        return 100.0
    elif diff >= 10:
        return linear_interpolate(diff, 10, 15, 90, 100)
    elif diff >= 5:
        return linear_interpolate(diff, 5, 10, 70, 90)
    elif diff >= 2:
        return linear_interpolate(diff, 2, 5, 40, 70)
    else:
        # Condensation imminent
        return linear_interpolate(diff, 0, 2, 10, 40)


def calculate_wind_stability_score(weather: WeatherData) -> float:
    """Calculate score based on wind conditions.

    Strong winds and high gusts create turbulence.
    Ideal: calm conditions with low gusts.

    Args:
        weather: Weather data

    Returns:
        Score 0-100
    """
    wind_speed = weather.wind_speed_10m  # m/s
    gusts = weather.wind_gusts  # m/s

    # Calculate gust ratio (indicator of turbulence)
    gust_ratio = gusts / max(wind_speed, 0.1)

    # Base score from wind speed
    # 0-2 m/s: excellent
    # 2-5 m/s: good
    # 5-10 m/s: fair
    # >10 m/s: poor
    if wind_speed <= 2:
        wind_score = 100.0
    elif wind_speed <= 5:
        wind_score = linear_interpolate(wind_speed, 2, 5, 80, 100)
    elif wind_speed <= 10:
        wind_score = linear_interpolate(wind_speed, 5, 10, 50, 80)
    else:
        wind_score = linear_interpolate(wind_speed, 10, 20, 20, 50)
        wind_score = max(10, wind_score)

    # Penalty for high gust ratio (turbulence indicator)
    # Gust ratio > 2 indicates gusty conditions
    if gust_ratio > 2:
        penalty = linear_interpolate(gust_ratio, 2, 4, 0, 30)
        wind_score -= penalty

    # Wind shear penalty if available
    if weather.wind_shear is not None:
        shear = weather.wind_shear  # m/s
        if shear > 5:
            shear_penalty = linear_interpolate(shear, 5, 15, 0, 20)
            wind_score -= shear_penalty

    return clamp(wind_score, 0, 100)


def calculate_humidity_score(weather: WeatherData) -> float:
    """Calculate score based on relative humidity.

    Lower humidity = less atmospheric absorption and refraction.
    Very high humidity (>90%) = poor conditions.
    But extremely low humidity (<20%) can also cause issues.

    Args:
        weather: Weather data

    Returns:
        Score 0-100
    """
    humidity = weather.humidity

    if humidity <= 30:
        return 100.0
    elif humidity <= 50:
        return linear_interpolate(humidity, 30, 50, 85, 100)
    elif humidity <= 70:
        return linear_interpolate(humidity, 50, 70, 60, 85)
    elif humidity <= 85:
        return linear_interpolate(humidity, 70, 85, 35, 60)
    elif humidity <= 95:
        return linear_interpolate(humidity, 85, 95, 15, 35)
    else:
        return linear_interpolate(humidity, 95, 100, 0, 15)


def calculate_cloud_cover_score(weather: WeatherData) -> float:
    """Calculate score based on cloud cover.

    Clear skies = 100, complete overcast = 0.
    High thin clouds (cirrus) are less problematic than low clouds.

    Args:
        weather: Weather data

    Returns:
        Score 0-100
    """
    total_cloud = weather.cloud_cover

    # Basic score from total cloud cover
    if total_cloud <= 5:
        base_score = 100.0
    elif total_cloud <= 20:
        base_score = linear_interpolate(total_cloud, 5, 20, 85, 100)
    elif total_cloud <= 50:
        base_score = linear_interpolate(total_cloud, 20, 50, 50, 85)
    elif total_cloud <= 80:
        base_score = linear_interpolate(total_cloud, 50, 80, 20, 50)
    else:
        base_score = linear_interpolate(total_cloud, 80, 100, 0, 20)

    # Adjust for cloud layer types if available
    if (
        weather.cloud_cover_low is not None
        and weather.cloud_cover_high is not None
    ):
        # Low clouds are worse than high clouds
        low_cloud = weather.cloud_cover_low
        high_cloud = weather.cloud_cover_high

        # If mostly high clouds (cirrus), improve score slightly
        if high_cloud > low_cloud * 2:
            bonus = min(10, (high_cloud - low_cloud) * 0.2)
            base_score = min(100, base_score + bonus)
        # If mostly low clouds, penalize
        elif low_cloud > high_cloud * 2:
            penalty = min(15, (low_cloud - high_cloud) * 0.3)
            base_score = max(0, base_score - penalty)

    return clamp(base_score, 0, 100)


def calculate_jet_stream_score(weather: WeatherData) -> float:
    """Calculate score based on jet stream speed.

    Strong jet stream overhead = high altitude turbulence = poor seeing.
    Jet stream < 30 m/s: minimal impact.
    Jet stream > 60 m/s: significant degradation.

    Args:
        weather: Weather data

    Returns:
        Score 0-100
    """
    if weather.jet_stream_speed is None:
        # No data available, assume neutral
        return 75.0

    jet_speed = weather.jet_stream_speed  # m/s

    if jet_speed <= 15:
        return 100.0
    elif jet_speed <= 30:
        return linear_interpolate(jet_speed, 15, 30, 85, 100)
    elif jet_speed <= 45:
        return linear_interpolate(jet_speed, 30, 45, 60, 85)
    elif jet_speed <= 60:
        return linear_interpolate(jet_speed, 45, 60, 35, 60)
    else:
        return linear_interpolate(jet_speed, 60, 100, 10, 35)


def calculate_pressure_stability_score(weather: WeatherData) -> float:
    """Calculate score based on atmospheric pressure.

    High, stable pressure generally indicates stable air.
    This is a secondary factor, less weight than others.

    Args:
        weather: Weather data

    Returns:
        Score 0-100
    """
    pressure = weather.pressure  # hPa

    # Optimal pressure range: 1015-1030 hPa (high pressure)
    if 1020 <= pressure <= 1030:
        return 100.0
    elif 1015 <= pressure < 1020:
        return linear_interpolate(pressure, 1015, 1020, 85, 100)
    elif 1030 < pressure <= 1040:
        return linear_interpolate(pressure, 1030, 1040, 100, 85)
    elif 1005 <= pressure < 1015:
        return linear_interpolate(pressure, 1005, 1015, 60, 85)
    elif 1000 <= pressure < 1005:
        return linear_interpolate(pressure, 1000, 1005, 40, 60)
    else:
        # Very low pressure (storm) or very high
        return 30.0


def calculate_moon_penalty(
    illumination: float,
    moon_altitude: float,
    is_deep_sky: bool = False,
) -> float:
    """Calculate moon penalty multiplier.

    Bright moon degrades deep-sky observation but not planets.
    Moon below horizon = no penalty.

    Args:
        illumination: Moon illumination percentage (0-100)
        moon_altitude: Moon altitude in degrees
        is_deep_sky: Whether target is a deep-sky object

    Returns:
        Penalty multiplier (0.5-1.0, where 1.0 = no penalty)
    """
    # Moon below horizon = no impact
    if moon_altitude <= 0:
        return 1.0

    # Planets/Moon don't care about lunar interference
    if not is_deep_sky:
        return 1.0

    # Calculate penalty based on illumination and altitude
    # Full moon high in sky = worst case
    altitude_factor = min(1.0, moon_altitude / 45)  # Max effect at 45 degrees
    illumination_factor = illumination / 100

    # Combined effect
    penalty_strength = altitude_factor * illumination_factor

    # Scale penalty: max 50% reduction for worst case
    return 1.0 - (penalty_strength * 0.5)


def calculate_airmass_penalty(airmass: float) -> float:
    """Calculate airmass penalty multiplier.

    Objects near horizon (high airmass) have degraded seeing.

    Args:
        airmass: Atmospheric airmass (1.0 at zenith)

    Returns:
        Penalty multiplier (0.5-1.0, where 1.0 = no penalty)
    """
    if airmass <= 1.2:
        return 1.0  # Excellent, no penalty
    elif airmass <= 1.5:
        return linear_interpolate(airmass, 1.2, 1.5, 0.95, 1.0)
    elif airmass <= 2.0:
        return linear_interpolate(airmass, 1.5, 2.0, 0.85, 0.95)
    elif airmass <= 3.0:
        return linear_interpolate(airmass, 2.0, 3.0, 0.65, 0.85)
    else:
        return linear_interpolate(airmass, 3.0, 5.0, 0.5, 0.65)


def calculate_precipitation_penalty(weather: WeatherData) -> float:
    """Calculate precipitation penalty multiplier.

    Any precipitation = very poor conditions.

    Args:
        weather: Weather data

    Returns:
        Penalty multiplier (0-1.0)
    """
    if weather.precipitation > 0:
        # Active precipitation = no observation possible
        return 0.1

    prob = weather.precipitation_probability or 0
    if prob > 80:
        return 0.3
    elif prob > 50:
        return linear_interpolate(prob, 50, 80, 0.6, 0.3)
    elif prob > 20:
        return linear_interpolate(prob, 20, 50, 0.9, 0.6)
    else:
        return 1.0
