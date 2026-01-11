"""Timelapse imaging session planner."""

import math
import statistics
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, Field

from astrosee.astronomy.calculator import AstronomyCalculator
from astrosee.astronomy.catalog import CelestialCatalog
from astrosee.astronomy.models import CelestialObject, Location
from astrosee.scoring.models import SeeingForecast
from astrosee.services.seeing import SeeingService


class MoonInterference(BaseModel):
    """Moon interference details during an imaging window."""

    rises_at: datetime | None = Field(default=None, description="Moon rise time in window")
    sets_at: datetime | None = Field(default=None, description="Moon set time in window")
    illumination: float = Field(description="Moon illumination percentage")
    min_angular_distance: float = Field(description="Minimum angular distance from target")
    avg_altitude: float = Field(description="Average moon altitude during window")
    severity: str = Field(description="Interference severity: none, minor, moderate, severe")


class TimelapseWindow(BaseModel):
    """A viable imaging window for a target."""

    target_name: str = Field(description="Target object name")
    target_description: str | None = Field(default=None, description="Target description")
    date: datetime = Field(description="Date of the window")
    start: datetime = Field(description="Window start time")
    end: datetime = Field(description="Window end time")
    start_altitude: float = Field(description="Target altitude at start")
    end_altitude: float = Field(description="Target altitude at end")
    start_azimuth: float = Field(description="Target azimuth at start")
    end_azimuth: float = Field(description="Target azimuth at end")
    peak_altitude: float = Field(description="Maximum target altitude")
    peak_time: datetime = Field(description="Time of peak altitude")
    average_score: float = Field(description="Average seeing score")
    min_score: float = Field(description="Minimum seeing score")
    max_score: float = Field(description="Maximum seeing score")
    moon_interference: MoonInterference | None = Field(default=None)
    altitude_profile: list[tuple[datetime, float]] = Field(
        default_factory=list, description="Altitude over time"
    )
    forecasts: list[SeeingForecast] = Field(default_factory=list)

    @property
    def duration_hours(self) -> float:
        """Get window duration in hours."""
        return (self.end - self.start).total_seconds() / 3600

    @property
    def duration_str(self) -> str:
        """Get duration as formatted string."""
        hours = int(self.duration_hours)
        minutes = int((self.duration_hours - hours) * 60)
        return f"{hours}h {minutes:02d}m"

    class Config:
        arbitrary_types_allowed = True


class TimelapseService:
    """Service for planning timelapse imaging sessions."""

    def __init__(
        self,
        seeing_service: SeeingService,
        calculator: AstronomyCalculator | None = None,
        catalog: CelestialCatalog | None = None,
    ):
        """Initialize timelapse service.

        Args:
            seeing_service: The seeing service for forecasts
            calculator: Astronomy calculator (uses one from seeing_service if not provided)
            catalog: Celestial catalog (uses one from seeing_service if not provided)
        """
        self.seeing = seeing_service
        self.calculator = calculator or seeing_service.astronomy
        self.catalog = catalog or seeing_service.catalog

    async def find_imaging_windows(
        self,
        target_name: str,
        location: Location,
        duration_hours: float = 4.0,
        min_altitude: float = 30.0,
        search_days: int = 7,
        target_date: datetime | None = None,
        min_score: float = 40.0,
    ) -> list[TimelapseWindow]:
        """Find optimal imaging windows for a target.

        Args:
            target_name: Name of the target object
            location: Observer location
            duration_hours: Minimum window duration in hours
            min_altitude: Minimum target altitude in degrees
            search_days: Days to search ahead
            target_date: Specific date to search (None = search all days)
            min_score: Minimum acceptable seeing score

        Returns:
            List of TimelapseWindow sorted by average score (best first)
        """
        # Resolve target
        target = self.catalog.search(target_name)
        if not target:
            return []

        # Get forecast data
        hours = search_days * 24
        forecasts = await self.seeing.get_forecast(location, hours)

        if not forecasts:
            return []

        # Build visibility data with altitude
        visibility_data = []
        for f in forecasts:
            pos = self.calculator.get_target_position(target, location, f.timestamp)
            visibility_data.append({
                "forecast": f,
                "altitude": pos.altitude,
                "azimuth": pos.azimuth,
                "is_visible": pos.altitude >= min_altitude,
            })

        # Filter by date if specified
        if target_date:
            target_date_str = target_date.strftime("%Y-%m-%d")
            visibility_data = [
                v for v in visibility_data
                if v["forecast"].timestamp.strftime("%Y-%m-%d") == target_date_str
            ]

        # Find contiguous windows where target is above min_altitude and it's night
        windows = self._find_altitude_windows(
            visibility_data,
            min_altitude=min_altitude,
            min_duration_hours=duration_hours,
            min_score=min_score,
        )

        # Create TimelapseWindow objects
        result = []
        for window_data in windows:
            window = self._create_timelapse_window(
                window_data,
                target,
                location,
            )
            if window:
                result.append(window)

        # Sort by average score (best first)
        result.sort(key=lambda w: w.average_score, reverse=True)

        return result

    def _find_altitude_windows(
        self,
        visibility_data: list[dict],
        min_altitude: float,
        min_duration_hours: float,
        min_score: float,
    ) -> list[list[dict]]:
        """Find contiguous windows where target is visible.

        Args:
            visibility_data: List of visibility data dicts
            min_altitude: Minimum altitude threshold
            min_duration_hours: Minimum window duration
            min_score: Minimum seeing score

        Returns:
            List of window data lists
        """
        windows = []
        current_window: list[dict] = []

        for v in visibility_data:
            f = v["forecast"]

            # Check if suitable: night, above altitude, decent score
            is_suitable = (
                f.is_night
                and v["altitude"] >= min_altitude
                and f.score.total_score >= min_score
            )

            if is_suitable:
                if not current_window:
                    current_window.append(v)
                else:
                    # Check continuity (within 2 hours)
                    time_diff = f.timestamp - current_window[-1]["forecast"].timestamp
                    if time_diff <= timedelta(hours=2):
                        current_window.append(v)
                    else:
                        # Save and start new window
                        if self._window_duration_hours(current_window) >= min_duration_hours:
                            windows.append(current_window)
                        current_window = [v]
            else:
                # End current window
                if current_window and self._window_duration_hours(current_window) >= min_duration_hours:
                    windows.append(current_window)
                current_window = []

        # Don't forget last window
        if current_window and self._window_duration_hours(current_window) >= min_duration_hours:
            windows.append(current_window)

        return windows

    def _window_duration_hours(self, window_data: list[dict]) -> float:
        """Calculate window duration in hours."""
        if len(window_data) < 2:
            return 1.0  # Single hour entry
        start = window_data[0]["forecast"].timestamp
        end = window_data[-1]["forecast"].timestamp
        return (end - start).total_seconds() / 3600

    def _create_timelapse_window(
        self,
        window_data: list[dict],
        target: CelestialObject,
        location: Location,
    ) -> TimelapseWindow | None:
        """Create a TimelapseWindow from window data.

        Args:
            window_data: List of visibility data dicts
            target: Target celestial object
            location: Observer location

        Returns:
            TimelapseWindow or None
        """
        if not window_data:
            return None

        forecasts = [v["forecast"] for v in window_data]
        altitudes = [v["altitude"] for v in window_data]
        azimuths = [v["azimuth"] for v in window_data]

        # Calculate scores
        scores = [f.score.total_score for f in forecasts]
        avg_score = statistics.mean(scores)
        min_score = min(scores)
        max_score = max(scores)

        # Find peak altitude
        peak_idx = altitudes.index(max(altitudes))
        peak_altitude = altitudes[peak_idx]
        peak_time = forecasts[peak_idx].timestamp

        # Build altitude profile (15-minute intervals for smooth chart)
        altitude_profile = self._calculate_altitude_profile(
            target, location,
            forecasts[0].timestamp,
            forecasts[-1].timestamp,
            interval_minutes=15,
        )

        # Calculate moon interference
        moon_interference = self._calculate_moon_interference(
            target, location,
            forecasts[0].timestamp,
            forecasts[-1].timestamp,
        )

        return TimelapseWindow(
            target_name=target.name,
            target_description=target.description,
            date=forecasts[0].timestamp.replace(hour=0, minute=0, second=0),
            start=forecasts[0].timestamp,
            end=forecasts[-1].timestamp,
            start_altitude=altitudes[0],
            end_altitude=altitudes[-1],
            start_azimuth=azimuths[0],
            end_azimuth=azimuths[-1],
            peak_altitude=peak_altitude,
            peak_time=peak_time,
            average_score=avg_score,
            min_score=min_score,
            max_score=max_score,
            moon_interference=moon_interference,
            altitude_profile=altitude_profile,
            forecasts=forecasts,
        )

    def _calculate_altitude_profile(
        self,
        target: CelestialObject,
        location: Location,
        start: datetime,
        end: datetime,
        interval_minutes: int = 15,
    ) -> list[tuple[datetime, float]]:
        """Calculate target altitude over time.

        Args:
            target: Target object
            location: Observer location
            start: Start time
            end: End time
            interval_minutes: Time interval in minutes

        Returns:
            List of (time, altitude) tuples
        """
        profile = []
        current = start

        while current <= end:
            pos = self.calculator.get_target_position(target, location, current)
            profile.append((current, pos.altitude))
            current += timedelta(minutes=interval_minutes)

        return profile

    def _calculate_moon_interference(
        self,
        target: CelestialObject,
        location: Location,
        start: datetime,
        end: datetime,
    ) -> MoonInterference:
        """Calculate moon interference during a window.

        Args:
            target: Target object
            location: Observer location
            start: Window start
            end: Window end

        Returns:
            MoonInterference with details
        """
        # Sample moon position hourly
        moon_data = []
        current = start

        while current <= end:
            moon_alt, moon_az = self.calculator.get_moon_position(location, current)
            target_pos = self.calculator.get_target_position(target, location, current)

            # Calculate angular distance
            angular_dist = self._angular_distance(
                target_pos.altitude, target_pos.azimuth,
                moon_alt, moon_az,
            )

            moon_data.append({
                "time": current,
                "altitude": moon_alt,
                "azimuth": moon_az,
                "angular_distance": angular_dist,
            })
            current += timedelta(hours=1)

        # Get moon illumination (use middle of window)
        mid_time = start + (end - start) / 2
        illumination = self.calculator.get_moon_illumination(mid_time)

        # Find rise/set times
        rises_at = None
        sets_at = None
        prev_alt = moon_data[0]["altitude"] if moon_data else 0

        for m in moon_data[1:]:
            if prev_alt <= 0 and m["altitude"] > 0:
                rises_at = m["time"]
            elif prev_alt > 0 and m["altitude"] <= 0:
                sets_at = m["time"]
            prev_alt = m["altitude"]

        # Calculate statistics
        altitudes = [m["altitude"] for m in moon_data]
        avg_altitude = statistics.mean(altitudes) if altitudes else 0
        min_angular_dist = min(m["angular_distance"] for m in moon_data) if moon_data else 180

        # Determine severity
        severity = self._calculate_interference_severity(
            illumination, avg_altitude, min_angular_dist
        )

        return MoonInterference(
            rises_at=rises_at,
            sets_at=sets_at,
            illumination=illumination,
            min_angular_distance=min_angular_dist,
            avg_altitude=avg_altitude,
            severity=severity,
        )

    def _angular_distance(
        self,
        alt1: float, az1: float,
        alt2: float, az2: float,
    ) -> float:
        """Calculate angular distance between two objects.

        Uses the spherical law of cosines.

        Args:
            alt1, az1: First object altitude and azimuth in degrees
            alt2, az2: Second object altitude and azimuth in degrees

        Returns:
            Angular distance in degrees
        """
        # Convert to radians
        alt1_rad = math.radians(alt1)
        alt2_rad = math.radians(alt2)
        az_diff_rad = math.radians(abs(az1 - az2))

        # Spherical law of cosines
        cos_dist = (
            math.sin(alt1_rad) * math.sin(alt2_rad) +
            math.cos(alt1_rad) * math.cos(alt2_rad) * math.cos(az_diff_rad)
        )

        # Clamp to [-1, 1] to avoid math domain errors
        cos_dist = max(-1, min(1, cos_dist))

        return math.degrees(math.acos(cos_dist))

    def _calculate_interference_severity(
        self,
        illumination: float,
        avg_altitude: float,
        min_angular_distance: float,
    ) -> str:
        """Calculate moon interference severity.

        Args:
            illumination: Moon illumination percentage
            avg_altitude: Average moon altitude
            min_angular_distance: Minimum angular distance from target

        Returns:
            Severity level: none, minor, moderate, severe
        """
        # Moon below horizon = no interference
        if avg_altitude <= 0:
            return "none"

        # Low illumination = minimal impact
        if illumination < 20:
            return "none" if min_angular_distance > 30 else "minor"

        # Calculate combined severity score
        illum_factor = illumination / 100
        alt_factor = min(1.0, max(0, avg_altitude / 45))
        dist_factor = max(0, 1 - min_angular_distance / 90)

        severity_score = illum_factor * alt_factor * (1 + dist_factor)

        if severity_score < 0.2:
            return "none"
        elif severity_score < 0.4:
            return "minor"
        elif severity_score < 0.7:
            return "moderate"
        else:
            return "severe"
