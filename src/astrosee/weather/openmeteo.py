"""OpenMeteo API client."""

import logging
from datetime import datetime, timezone

import httpx

from astrosee.core.exceptions import WeatherAPIError
from astrosee.weather.models import WeatherData

logger = logging.getLogger(__name__)


class OpenMeteoClient:
    """Client for the Open-Meteo API (free, no API key required)."""

    BASE_URL = "https://api.open-meteo.com/v1/forecast"
    TIMEOUT = 30.0

    # Variables we request from the API
    HOURLY_VARIABLES = [
        "temperature_2m",
        "dew_point_2m",
        "relative_humidity_2m",
        "pressure_msl",
        "cloud_cover",
        "cloud_cover_low",
        "cloud_cover_mid",
        "cloud_cover_high",
        "wind_speed_10m",
        "wind_speed_80m",
        "wind_gusts_10m",
        "wind_direction_10m",
        "precipitation",
        "precipitation_probability",
        "visibility",
        "temperature_850hPa",
    ]

    def __init__(self, client: httpx.AsyncClient | None = None):
        """Initialize the client.

        Args:
            client: Optional httpx client (for testing/reuse)
        """
        self._client = client
        self._owns_client = client is None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.TIMEOUT)
        return self._client

    async def close(self) -> None:
        """Close the HTTP client if we own it."""
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get_current(self, lat: float, lon: float) -> WeatherData:
        """Get current weather conditions.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            Current weather data
        """
        forecast = await self.get_forecast(lat, lon, hours=1)
        if not forecast:
            raise WeatherAPIError("No forecast data available", source="OpenMeteo")
        return forecast[0]

    async def get_forecast(
        self, lat: float, lon: float, hours: int = 48
    ) -> list[WeatherData]:
        """Get weather forecast.

        Args:
            lat: Latitude
            lon: Longitude
            hours: Number of hours to forecast (max 384 = 16 days)

        Returns:
            List of hourly weather data
        """
        client = await self._get_client()

        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": ",".join(self.HOURLY_VARIABLES),
            "forecast_hours": min(hours, 384),
            "timezone": "UTC",
        }

        try:
            response = await client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            raise WeatherAPIError(
                f"HTTP {e.response.status_code}: {e.response.text}",
                source="OpenMeteo",
            ) from e
        except httpx.RequestError as e:
            raise WeatherAPIError(
                f"Request failed: {e}",
                source="OpenMeteo",
            ) from e

        return self._parse_response(data)

    def _parse_response(self, data: dict) -> list[WeatherData]:
        """Parse the API response into WeatherData objects."""
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])

        if not times:
            return []

        result = []
        for i, time_str in enumerate(times):
            try:
                # Parse ISO timestamp
                timestamp = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)

                weather = WeatherData(
                    timestamp=timestamp,
                    temperature=self._get_value(hourly, "temperature_2m", i, 0.0),
                    temperature_850hpa=self._get_value(hourly, "temperature_850hPa", i),
                    dew_point=self._get_value(hourly, "dew_point_2m", i, 0.0),
                    wind_speed_10m=self._get_value(hourly, "wind_speed_10m", i, 0.0) / 3.6,  # km/h to m/s
                    wind_speed_80m=self._safe_divide(
                        self._get_value(hourly, "wind_speed_80m", i), 3.6
                    ),
                    wind_gusts=self._get_value(hourly, "wind_gusts_10m", i, 0.0) / 3.6,
                    wind_direction=self._get_value(hourly, "wind_direction_10m", i, 0.0),
                    humidity=self._get_value(hourly, "relative_humidity_2m", i, 50.0),
                    cloud_cover=self._get_value(hourly, "cloud_cover", i, 0.0),
                    cloud_cover_low=self._get_value(hourly, "cloud_cover_low", i),
                    cloud_cover_mid=self._get_value(hourly, "cloud_cover_mid", i),
                    cloud_cover_high=self._get_value(hourly, "cloud_cover_high", i),
                    pressure=self._get_value(hourly, "pressure_msl", i, 1013.25),
                    precipitation=self._get_value(hourly, "precipitation", i, 0.0),
                    precipitation_probability=self._get_value(
                        hourly, "precipitation_probability", i
                    ),
                    visibility=self._get_value(hourly, "visibility", i),
                )
                result.append(weather)
            except (ValueError, KeyError) as e:
                logger.warning(f"Failed to parse weather data at index {i}: {e}")
                continue

        return result

    @staticmethod
    def _get_value(
        hourly: dict,
        key: str,
        index: int,
        default: float | None = None,
    ) -> float | None:
        """Safely get a value from the hourly data."""
        values = hourly.get(key, [])
        if index < len(values) and values[index] is not None:
            return float(values[index])
        return default

    @staticmethod
    def _safe_divide(value: float | None, divisor: float) -> float | None:
        """Safely divide a value that might be None."""
        if value is None:
            return None
        return value / divisor
