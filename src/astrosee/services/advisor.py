"""Equipment and activity advisor service."""

from dataclasses import dataclass, field
from datetime import datetime

from astrosee.astronomy.calculator import AstronomyCalculator
from astrosee.astronomy.catalog import CelestialCatalog
from astrosee.astronomy.models import Location
from astrosee.scoring.models import SeeingReport


# Activity profiles with condition requirements
ACTIVITY_PROFILES = {
    "visual": {
        "min_score": 40,
        "ideal_score": 70,
        "wind_tolerance": 10.0,  # m/s
        "moon_tolerance": 0.8,  # high tolerance
        "cloud_max": 50,
    },
    "planetary_imaging": {
        "min_score": 70,
        "ideal_score": 90,
        "wind_tolerance": 3.0,  # very sensitive
        "moon_tolerance": 1.0,  # doesn't matter
        "cloud_max": 20,
    },
    "deep_sky_imaging": {
        "min_score": 60,
        "ideal_score": 85,
        "wind_tolerance": 5.0,
        "moon_tolerance": 0.3,  # low tolerance
        "cloud_max": 15,
    },
    "widefield": {
        "min_score": 50,
        "ideal_score": 75,
        "wind_tolerance": 8.0,
        "moon_tolerance": 0.4,  # low tolerance
        "cloud_max": 25,
    },
}


@dataclass
class ActivityRecommendation:
    """Recommendation for an activity type."""

    activity: str
    score: float  # 0-100 suitability score
    rating: str  # Excellent, Very Good, Good, Fair, Poor
    issues: list[str] = field(default_factory=list)


@dataclass
class EquipmentSuggestion:
    """Equipment or technique suggestion."""

    icon: str
    text: str
    priority: str  # high, medium, low


@dataclass
class TargetRecommendation:
    """Recommended target for observation."""

    name: str
    description: str | None
    altitude: float
    score: float  # Suitability score
    activity_type: str  # visual, planetary, deep_sky


class AdvisorService:
    """Provides equipment and activity recommendations."""

    def __init__(
        self,
        calculator: AstronomyCalculator,
        catalog: CelestialCatalog,
    ):
        """Initialize advisor service.

        Args:
            calculator: Astronomy calculator for position calculations
            catalog: Celestial catalog for target recommendations
        """
        self.calculator = calculator
        self.catalog = catalog

    def get_activity_recommendations(
        self,
        report: SeeingReport,
    ) -> list[ActivityRecommendation]:
        """Score each activity type based on conditions.

        Args:
            report: Current seeing report

        Returns:
            List of activity recommendations sorted by score
        """
        recommendations = []

        for activity, profile in ACTIVITY_PROFILES.items():
            score, issues = self._calculate_activity_score(report, activity, profile)
            rating = self._score_to_rating(score)
            recommendations.append(
                ActivityRecommendation(
                    activity=activity,
                    score=score,
                    rating=rating,
                    issues=issues,
                )
            )

        # Sort by score (best first)
        recommendations.sort(key=lambda r: r.score, reverse=True)
        return recommendations

    def _calculate_activity_score(
        self,
        report: SeeingReport,
        activity: str,
        profile: dict,
    ) -> tuple[float, list[str]]:
        """Calculate suitability score for an activity.

        Args:
            report: Seeing report
            activity: Activity type
            profile: Activity profile with requirements

        Returns:
            Tuple of (score, list of issues)
        """
        base_score = report.score.total_score
        issues = []
        multiplier = 1.0

        # Wind penalty
        wind = report.weather.wind_speed_10m or 0
        if wind > profile["wind_tolerance"]:
            over = (wind - profile["wind_tolerance"]) / profile["wind_tolerance"]
            multiplier *= max(0.3, 1 - over * 0.5)
            issues.append(f"Wind {wind:.1f} m/s exceeds ideal")

        # Moon penalty for deep-sky activities
        if activity in ("deep_sky_imaging", "widefield"):
            moon_illum = report.astronomy.moon_illumination / 100
            moon_alt = report.astronomy.moon_altitude
            if moon_alt > 0 and moon_illum > profile["moon_tolerance"]:
                penalty = (moon_illum - profile["moon_tolerance"]) * 0.5
                multiplier *= max(0.5, 1 - penalty)
                issues.append(f"Moon {int(moon_illum * 100)}% may interfere")

        # Cloud penalty
        clouds = report.weather.cloud_cover or 0
        if clouds > profile["cloud_max"]:
            over = (clouds - profile["cloud_max"]) / 100
            multiplier *= max(0.2, 1 - over)
            issues.append(f"Cloud cover {clouds:.0f}% limits visibility")

        # Calculate final score
        final = base_score * multiplier

        # Boost if conditions are ideal
        if base_score >= profile["ideal_score"] and not issues:
            final = min(100, final * 1.1)

        return final, issues

    def _score_to_rating(self, score: float) -> str:
        """Convert score to rating text.

        Args:
            score: Numeric score 0-100

        Returns:
            Rating text
        """
        if score >= 85:
            return "Excellent"
        elif score >= 70:
            return "Very Good"
        elif score >= 55:
            return "Good"
        elif score >= 40:
            return "Fair"
        else:
            return "Poor"

    def get_equipment_suggestions(
        self,
        report: SeeingReport,
    ) -> list[EquipmentSuggestion]:
        """Get equipment suggestions based on conditions.

        Args:
            report: Current seeing report

        Returns:
            List of equipment suggestions sorted by priority
        """
        suggestions = []
        weather = report.weather

        # Temperature differential / dew risk
        temp_diff = weather.temperature_differential or 10
        if temp_diff < 3:
            suggestions.append(
                EquipmentSuggestion(
                    icon="🌡️",
                    text="High dew risk - use dew heaters on optics",
                    priority="high",
                )
            )
        elif temp_diff < 5:
            suggestions.append(
                EquipmentSuggestion(
                    icon="💧",
                    text="Moderate dew risk - have dew shields ready",
                    priority="medium",
                )
            )

        # Wind conditions
        wind = weather.wind_speed_10m or 0
        if wind > 8:
            suggestions.append(
                EquipmentSuggestion(
                    icon="💨",
                    text=f"Strong wind ({wind:.0f} m/s) - use wind shields",
                    priority="high",
                )
            )
        elif wind > 5:
            suggestions.append(
                EquipmentSuggestion(
                    icon="🌬️",
                    text="Moderate wind - vibration damping recommended",
                    priority="medium",
                )
            )
        elif wind < 2:
            suggestions.append(
                EquipmentSuggestion(
                    icon="✨",
                    text="Calm conditions - ideal for high magnification",
                    priority="low",
                )
            )

        # Humidity
        humidity = weather.humidity or 50
        if humidity > 90:
            suggestions.append(
                EquipmentSuggestion(
                    icon="💦",
                    text="Very high humidity - protect mirrors and lenses",
                    priority="high",
                )
            )
        elif humidity < 40:
            suggestions.append(
                EquipmentSuggestion(
                    icon="🌙",
                    text="Low humidity - excellent optical conditions",
                    priority="low",
                )
            )

        # Moon position
        moon_illum = report.astronomy.moon_illumination
        moon_alt = report.astronomy.moon_altitude
        if moon_alt <= 0:
            suggestions.append(
                EquipmentSuggestion(
                    icon="🌑",
                    text="Moon below horizon - perfect for deep-sky",
                    priority="low",
                )
            )
        elif moon_illum > 70:
            suggestions.append(
                EquipmentSuggestion(
                    icon="🌕",
                    text=f"Bright moon ({moon_illum:.0f}%) - use narrowband filters",
                    priority="medium",
                )
            )

        # Cloud cover
        clouds = weather.cloud_cover or 0
        if clouds > 60:
            suggestions.append(
                EquipmentSuggestion(
                    icon="☁️",
                    text="High cloud cover - monitor for clearing",
                    priority="medium",
                )
            )

        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        suggestions.sort(key=lambda s: priority_order[s.priority])

        return suggestions

    def get_target_recommendations(
        self,
        report: SeeingReport,
        location: Location,
        time: datetime,
        limit: int = 5,
    ) -> list[TargetRecommendation]:
        """Get recommended targets for current conditions.

        Args:
            report: Current seeing report
            location: Observer location
            time: Time of observation
            limit: Maximum number of recommendations

        Returns:
            List of target recommendations sorted by score
        """
        recommendations = []

        # Get visible objects
        visible = self.catalog.get_visible(
            location=location,
            time=time,
            min_altitude=20,
            calculator=self.calculator,
        )

        moon_illum = report.astronomy.moon_illumination
        base_score = report.score.total_score

        for obj, altitude, _ in visible[:20]:  # Check top 20 by altitude
            # Calculate target-specific score
            score = base_score

            # Airmass penalty
            airmass = self.calculator.get_airmass(altitude)
            if airmass > 2.0:
                score *= 0.8
            elif airmass > 1.5:
                score *= 0.9

            # Deep-sky moon penalty
            if obj.is_deep_sky and moon_illum > 50:
                if report.astronomy.moon_altitude > 0:
                    score *= max(0.5, 1 - moon_illum / 200)

            # Determine best activity type
            obj_type = obj.object_type.value if hasattr(obj.object_type, "value") else str(obj.object_type)
            if obj_type == "planet":
                activity = "planetary"
            elif obj.is_deep_sky:
                if obj_type in ("galaxy", "nebula"):
                    activity = "deep_sky"
                else:
                    activity = "visual"
            else:
                activity = "visual"

            recommendations.append(
                TargetRecommendation(
                    name=obj.name,
                    description=obj.description,
                    altitude=altitude,
                    score=score,
                    activity_type=activity,
                )
            )

        # Sort by score and limit
        recommendations.sort(key=lambda r: r.score, reverse=True)
        return recommendations[:limit]
