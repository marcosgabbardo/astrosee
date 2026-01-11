"""Scoring data models."""

from datetime import datetime, timedelta

from pydantic import BaseModel, Field

from astrosee.astronomy.models import AstronomyData, CelestialObject, Location, TargetPosition
from astrosee.weather.models import WeatherData


class SeeingScore(BaseModel):
    """Calculated seeing score with component breakdown."""

    total_score: float = Field(ge=0, le=100, description="Overall seeing score 0-100")

    # Component scores
    component_scores: dict[str, float] = Field(
        description="Individual component scores"
    )

    # Penalties applied
    penalties: dict[str, float] = Field(
        default_factory=dict, description="Penalty multipliers applied"
    )

    timestamp: datetime = Field(description="Time of calculation")

    @property
    def rating(self) -> str:
        """Get a human-readable rating."""
        if self.total_score >= 85:
            return "Excellent"
        elif self.total_score >= 70:
            return "Very Good"
        elif self.total_score >= 55:
            return "Good"
        elif self.total_score >= 40:
            return "Fair"
        elif self.total_score >= 25:
            return "Poor"
        else:
            return "Bad"

    @property
    def rating_color(self) -> str:
        """Get a color for the rating (for Rich display)."""
        if self.total_score >= 85:
            return "bright_green"
        elif self.total_score >= 70:
            return "green"
        elif self.total_score >= 55:
            return "yellow"
        elif self.total_score >= 40:
            return "orange1"
        elif self.total_score >= 25:
            return "red"
        else:
            return "bright_red"

    @property
    def recommendation(self) -> str:
        """Get observation recommendation."""
        if self.total_score >= 85:
            return "Outstanding conditions! Perfect for imaging and visual observation."
        elif self.total_score >= 70:
            return "Very good conditions. Excellent for most observations."
        elif self.total_score >= 55:
            return "Good conditions. Suitable for planetary and bright deep-sky objects."
        elif self.total_score >= 40:
            return "Fair conditions. Best for planets and the Moon."
        elif self.total_score >= 25:
            return "Poor conditions. Only bright objects recommended."
        else:
            return "Not recommended for serious observation tonight."


class SeeingReport(BaseModel):
    """Complete seeing report for a specific time and location."""

    location: Location
    timestamp: datetime
    weather: WeatherData
    astronomy: AstronomyData
    score: SeeingScore

    # Optional target-specific data
    target: CelestialObject | None = None
    target_position: TargetPosition | None = None

    @property
    def summary(self) -> str:
        """Get a one-line summary."""
        target_info = ""
        if self.target:
            target_info = f" for {self.target.name}"
        return (
            f"Score: {self.score.total_score:.0f}/100 ({self.score.rating}){target_info} "
            f"at {self.location.name}"
        )


class SeeingForecast(BaseModel):
    """Single forecast entry (simpler than full report)."""

    timestamp: datetime
    score: SeeingScore
    weather: WeatherData
    moon_illumination: float
    moon_altitude: float
    is_night: bool

    @property
    def is_observable(self) -> bool:
        """Check if conditions allow observation."""
        return self.is_night and self.weather.cloud_cover < 80


class ObservingWindow(BaseModel):
    """Optimal observation window."""

    start: datetime
    end: datetime
    average_score: float
    peak_score: float
    peak_time: datetime
    forecasts: list[SeeingForecast]

    @property
    def duration(self) -> timedelta:
        """Duration of the window."""
        return self.end - self.start

    @property
    def duration_hours(self) -> float:
        """Duration in hours."""
        return self.duration.total_seconds() / 3600

    def __str__(self) -> str:
        return (
            f"{self.start.strftime('%H:%M')} - {self.end.strftime('%H:%M')} "
            f"(avg: {self.average_score:.0f}, peak: {self.peak_score:.0f})"
        )


class LocationComparison(BaseModel):
    """Comparison of seeing at multiple locations."""

    timestamp: datetime
    locations: list[Location]
    reports: list[SeeingReport]

    @property
    def best_location(self) -> tuple[Location, SeeingReport]:
        """Get the location with the best score."""
        best_idx = max(
            range(len(self.reports)),
            key=lambda i: self.reports[i].score.total_score,
        )
        return self.locations[best_idx], self.reports[best_idx]

    def ranked(self) -> list[tuple[Location, SeeingReport]]:
        """Get locations ranked by score (best first)."""
        pairs = list(zip(self.locations, self.reports))
        return sorted(pairs, key=lambda p: p[1].score.total_score, reverse=True)
