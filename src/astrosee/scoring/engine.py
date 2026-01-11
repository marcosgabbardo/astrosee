"""Seeing score calculation engine."""

from datetime import datetime, timezone

from astrosee.scoring.components import (
    calculate_airmass_penalty,
    calculate_cloud_cover_score,
    calculate_humidity_score,
    calculate_jet_stream_score,
    calculate_moon_penalty,
    calculate_precipitation_penalty,
    calculate_temperature_differential_score,
    calculate_wind_stability_score,
)
from astrosee.scoring.models import SeeingScore
from astrosee.weather.models import WeatherData


class ScoringEngine:
    """Engine for calculating seeing scores from weather data."""

    # Default component weights (must sum to 1.0)
    DEFAULT_WEIGHTS = {
        "temperature_differential": 0.25,
        "wind_stability": 0.30,
        "humidity": 0.15,
        "cloud_cover": 0.20,
        "jet_stream": 0.10,
    }

    def __init__(self, weights: dict[str, float] | None = None):
        """Initialize the scoring engine.

        Args:
            weights: Custom component weights (default: DEFAULT_WEIGHTS)
        """
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()

        # Validate weights sum to 1.0
        total = sum(self.weights.values())
        if abs(total - 1.0) > 0.01:
            # Normalize weights
            for key in self.weights:
                self.weights[key] /= total

    def calculate_score(
        self,
        weather: WeatherData,
        moon_illumination: float = 0.0,
        moon_altitude: float = -90.0,
        airmass: float | None = None,
        is_deep_sky: bool = False,
    ) -> SeeingScore:
        """Calculate seeing score from weather and astronomical data.

        Args:
            weather: Weather data
            moon_illumination: Moon illumination percentage (0-100)
            moon_altitude: Moon altitude in degrees
            airmass: Target airmass (None if no specific target)
            is_deep_sky: Whether target is a deep-sky object

        Returns:
            SeeingScore with total score and breakdown
        """
        # Calculate component scores
        components = {
            "temperature_differential": calculate_temperature_differential_score(weather),
            "wind_stability": calculate_wind_stability_score(weather),
            "humidity": calculate_humidity_score(weather),
            "cloud_cover": calculate_cloud_cover_score(weather),
            "jet_stream": calculate_jet_stream_score(weather),
        }

        # Calculate weighted average
        base_score = sum(
            components[key] * self.weights[key]
            for key in components
        )

        # Calculate penalties
        penalties = {}

        # Moon penalty (for deep-sky objects)
        moon_penalty = calculate_moon_penalty(
            moon_illumination, moon_altitude, is_deep_sky
        )
        if moon_penalty < 1.0:
            penalties["moon"] = moon_penalty

        # Airmass penalty (for specific targets)
        airmass_penalty = 1.0
        if airmass is not None:
            airmass_penalty = calculate_airmass_penalty(airmass)
            if airmass_penalty < 1.0:
                penalties["airmass"] = airmass_penalty

        # Precipitation penalty
        precip_penalty = calculate_precipitation_penalty(weather)
        if precip_penalty < 1.0:
            penalties["precipitation"] = precip_penalty

        # Apply penalties
        final_score = base_score
        for penalty in penalties.values():
            final_score *= penalty

        # Ensure score is in valid range
        final_score = max(0, min(100, final_score))

        return SeeingScore(
            total_score=round(final_score, 1),
            component_scores=components,
            penalties=penalties,
            timestamp=weather.timestamp,
        )

    def calculate_score_simple(self, weather: WeatherData) -> float:
        """Calculate a simple seeing score without astronomical factors.

        Useful for quick forecasts where target is not specified.

        Args:
            weather: Weather data

        Returns:
            Score 0-100
        """
        score = self.calculate_score(weather)
        return score.total_score

    def get_recommendations(
        self,
        score: SeeingScore,
        weather: WeatherData,
    ) -> list[str]:
        """Get recommendations based on score and conditions.

        Args:
            score: Calculated seeing score
            weather: Weather data

        Returns:
            List of recommendation strings
        """
        recommendations = []

        # Overall recommendation
        if score.total_score >= 85:
            recommendations.append(
                "Outstanding conditions for all types of observation and imaging."
            )
        elif score.total_score >= 70:
            recommendations.append(
                "Very good conditions. Excellent for planetary and deep-sky observation."
            )
        elif score.total_score >= 55:
            recommendations.append(
                "Good conditions. Suitable for most visual observation."
            )
        elif score.total_score >= 40:
            recommendations.append(
                "Fair conditions. Best for planetary observation and the Moon."
            )
        else:
            recommendations.append(
                "Poor conditions. Consider rescheduling if possible."
            )

        # Specific recommendations based on components
        components = score.component_scores

        if components.get("cloud_cover", 100) < 50:
            if weather.cloud_cover > 50:
                recommendations.append(
                    f"Cloud cover at {weather.cloud_cover:.0f}% may obstruct targets. "
                    "Monitor for clearing."
                )

        if components.get("wind_stability", 100) < 60:
            recommendations.append(
                f"Wind at {weather.wind_speed_10m:.1f} m/s may cause tracking issues. "
                "Shield your setup if possible."
            )

        if components.get("humidity", 100) < 60:
            if weather.temperature_differential < 3:
                recommendations.append(
                    "High humidity risk. Watch for dew formation on optics."
                )

        if components.get("temperature_differential", 100) < 50:
            recommendations.append(
                "Temperature differential is low. Thermal equilibration may take longer."
            )

        # Moon recommendations
        if "moon" in score.penalties:
            penalty = score.penalties["moon"]
            if penalty < 0.7:
                recommendations.append(
                    "Bright Moon affecting deep-sky observation. "
                    "Consider planetary targets or wait for moonset."
                )

        return recommendations

    def get_best_targets(
        self,
        score: SeeingScore,
        weather: WeatherData,
    ) -> dict[str, str]:
        """Get recommendations for target types.

        Args:
            score: Calculated seeing score
            weather: Weather data

        Returns:
            Dict mapping target type to recommendation
        """
        total = score.total_score
        targets = {}

        # Planets
        if total >= 60 or (total >= 40 and weather.cloud_cover < 30):
            targets["planets"] = "Excellent" if total >= 80 else "Good"
        elif total >= 30:
            targets["planets"] = "Fair"
        else:
            targets["planets"] = "Poor"

        # Moon
        targets["moon"] = "Excellent" if total >= 50 else "Good" if total >= 30 else "Fair"

        # Deep sky
        moon_penalty = score.penalties.get("moon", 1.0)
        effective_deep_sky = total * moon_penalty
        if effective_deep_sky >= 70:
            targets["deep_sky"] = "Excellent"
        elif effective_deep_sky >= 50:
            targets["deep_sky"] = "Good"
        elif effective_deep_sky >= 35:
            targets["deep_sky"] = "Fair"
        else:
            targets["deep_sky"] = "Poor"

        # Imaging
        if total >= 80 and weather.wind_speed_10m < 3:
            targets["imaging"] = "Excellent"
        elif total >= 65 and weather.wind_speed_10m < 5:
            targets["imaging"] = "Good"
        elif total >= 50:
            targets["imaging"] = "Fair"
        else:
            targets["imaging"] = "Not recommended"

        return targets
