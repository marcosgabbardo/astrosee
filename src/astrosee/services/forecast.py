"""Forecast analysis service."""

import statistics
from datetime import datetime, timedelta, timezone

from astrosee.astronomy.models import Location
from astrosee.scoring.models import LocationComparison, ObservingWindow, SeeingForecast, SeeingReport
from astrosee.services.seeing import SeeingService


class ForecastService:
    """Service for forecast analysis and optimization."""

    def __init__(self, seeing_service: SeeingService):
        """Initialize forecast service.

        Args:
            seeing_service: The main seeing service
        """
        self.seeing = seeing_service

    async def find_best_window(
        self,
        location: Location,
        hours: int = 48,
        min_score: float = 50,
        min_duration_hours: int = 2,
    ) -> ObservingWindow | None:
        """Find the best observation window in the forecast period.

        Args:
            location: Observer location
            hours: Hours to search
            min_score: Minimum acceptable score
            min_duration_hours: Minimum window duration in hours

        Returns:
            Best ObservingWindow or None if no suitable window found
        """
        forecasts = await self.seeing.get_forecast(location, hours)

        if not forecasts:
            return None

        # Filter to nighttime hours with minimum score
        suitable = [
            f for f in forecasts
            if f.is_night and f.score.total_score >= min_score
        ]

        if len(suitable) < min_duration_hours:
            return None

        # Find contiguous windows
        windows = self._find_contiguous_windows(suitable, min_duration_hours)

        if not windows:
            return None

        # Find best window by average score
        best_window = max(windows, key=lambda w: w.average_score)

        return best_window

    def _find_contiguous_windows(
        self,
        forecasts: list[SeeingForecast],
        min_hours: int,
    ) -> list[ObservingWindow]:
        """Find contiguous observation windows.

        Args:
            forecasts: Suitable forecast entries
            min_hours: Minimum window duration

        Returns:
            List of observation windows
        """
        if not forecasts:
            return []

        windows = []
        current_window: list[SeeingForecast] = []

        for i, f in enumerate(forecasts):
            if not current_window:
                current_window.append(f)
                continue

            # Check if contiguous (within 2 hours)
            time_diff = f.timestamp - current_window[-1].timestamp
            if time_diff <= timedelta(hours=2):
                current_window.append(f)
            else:
                # Save current window if long enough
                if len(current_window) >= min_hours:
                    windows.append(self._create_window(current_window))
                current_window = [f]

        # Don't forget the last window
        if len(current_window) >= min_hours:
            windows.append(self._create_window(current_window))

        return windows

    def _create_window(
        self,
        forecasts: list[SeeingForecast],
    ) -> ObservingWindow:
        """Create an ObservingWindow from forecasts.

        Args:
            forecasts: List of contiguous forecasts

        Returns:
            ObservingWindow
        """
        scores = [f.score.total_score for f in forecasts]
        avg_score = statistics.mean(scores)
        peak_score = max(scores)
        peak_idx = scores.index(peak_score)

        return ObservingWindow(
            start=forecasts[0].timestamp,
            end=forecasts[-1].timestamp,
            average_score=avg_score,
            peak_score=peak_score,
            peak_time=forecasts[peak_idx].timestamp,
            forecasts=forecasts,
        )

    async def compare_locations(
        self,
        locations: list[Location],
        time: datetime | None = None,
    ) -> LocationComparison:
        """Compare seeing conditions at multiple locations.

        Args:
            locations: List of locations to compare
            time: Time for comparison (default: now)

        Returns:
            LocationComparison with ranked results
        """
        if time is None:
            time = datetime.now(timezone.utc)

        reports = []
        for loc in locations:
            report = await self.seeing.get_current_conditions(loc)
            reports.append(report)

        return LocationComparison(
            timestamp=time,
            locations=locations,
            reports=reports,
        )

    async def get_best_nights(
        self,
        location: Location,
        days: int = 7,
        min_score: float = 60,
    ) -> list[tuple[datetime, float, str]]:
        """Find the best nights in the forecast period.

        Args:
            location: Observer location
            days: Number of days to analyze
            min_score: Minimum score to consider

        Returns:
            List of (date, average_score, summary) tuples for best nights
        """
        hours = days * 24
        forecasts = await self.seeing.get_forecast(location, hours)

        # Group by night
        nights: dict[str, list[SeeingForecast]] = {}
        for f in forecasts:
            if not f.is_night:
                continue
            night_key = f.timestamp.strftime("%Y-%m-%d")
            if night_key not in nights:
                nights[night_key] = []
            nights[night_key].append(f)

        # Calculate average score per night
        results = []
        for night_key, night_forecasts in nights.items():
            if not night_forecasts:
                continue

            avg_score = statistics.mean(f.score.total_score for f in night_forecasts)
            if avg_score < min_score:
                continue

            # Generate summary
            cloud_avg = statistics.mean(f.weather.cloud_cover for f in night_forecasts)
            wind_avg = statistics.mean(f.weather.wind_speed_10m for f in night_forecasts)

            summary_parts = []
            if avg_score >= 80:
                summary_parts.append("Excellent")
            elif avg_score >= 65:
                summary_parts.append("Very good")
            else:
                summary_parts.append("Good")

            if cloud_avg < 20:
                summary_parts.append("clear skies")
            elif cloud_avg < 50:
                summary_parts.append("partly cloudy")
            else:
                summary_parts.append("variable clouds")

            if wind_avg < 3:
                summary_parts.append("calm")
            elif wind_avg < 7:
                summary_parts.append("light wind")

            night_date = datetime.strptime(night_key, "%Y-%m-%d")
            results.append((night_date, avg_score, ". ".join(summary_parts)))

        # Sort by score
        results.sort(key=lambda x: x[1], reverse=True)

        return results

    async def get_target_visibility(
        self,
        location: Location,
        target_name: str,
        hours: int = 24,
    ) -> list[dict]:
        """Get target visibility over time.

        Args:
            location: Observer location
            target_name: Target object name
            hours: Hours to analyze

        Returns:
            List of dicts with time, altitude, airmass, score
        """
        target = self.seeing.catalog.search(target_name)
        if not target:
            return []

        forecasts = await self.seeing.get_forecast(location, hours, target=target)

        results = []
        for f in forecasts:
            pos = self.seeing.astronomy.get_target_position(
                target, location, f.timestamp
            )

            results.append({
                "time": f.timestamp,
                "altitude": pos.altitude,
                "azimuth": pos.azimuth,
                "airmass": pos.airmass,
                "is_visible": pos.is_visible,
                "score": f.score.total_score,
                "is_night": f.is_night,
                "cloud_cover": f.weather.cloud_cover,
            })

        return results
