"""Weather provider protocols (interfaces)."""

from datetime import datetime
from typing import Protocol

from astrosee.weather.models import WeatherData


class WeatherProvider(Protocol):
    """Protocol for weather data providers."""

    async def get_current(self, lat: float, lon: float) -> WeatherData:
        """Get current weather conditions.

        Args:
            lat: Latitude in degrees
            lon: Longitude in degrees

        Returns:
            Current weather data
        """
        ...

    async def get_forecast(
        self, lat: float, lon: float, hours: int = 48
    ) -> list[WeatherData]:
        """Get weather forecast.

        Args:
            lat: Latitude in degrees
            lon: Longitude in degrees
            hours: Number of hours to forecast

        Returns:
            List of hourly weather data
        """
        ...


class JetStreamProvider(Protocol):
    """Protocol for jet stream / upper atmosphere data."""

    async def get_jet_stream_speed(
        self, lat: float, lon: float, time: datetime
    ) -> float | None:
        """Get jet stream wind speed at 250hPa level.

        Args:
            lat: Latitude in degrees
            lon: Longitude in degrees
            time: Time for the data

        Returns:
            Wind speed in m/s at jet stream level, or None if unavailable
        """
        ...
