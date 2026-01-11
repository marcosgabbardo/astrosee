"""NOAA GFS model client for jet stream data.

Uses Open-Meteo's GFS endpoint which provides access to NOAA GFS model data
including upper atmosphere variables like winds at 250hPa (jet stream level).
"""

import logging
from datetime import datetime, timezone

import httpx

from astrosee.core.exceptions import WeatherAPIError

logger = logging.getLogger(__name__)


class NoaaGfsClient:
    """Client for NOAA GFS model data via Open-Meteo.

    The Open-Meteo GFS API provides access to NOAA's Global Forecast System
    model data, including upper atmosphere winds at various pressure levels.
    """

    BASE_URL = "https://api.open-meteo.com/v1/gfs"
    TIMEOUT = 30.0

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

    async def get_jet_stream_speed(
        self, lat: float, lon: float, time: datetime
    ) -> float | None:
        """Get jet stream wind speed at 250hPa level.

        The jet stream typically flows at around 250hPa (approximately 10km altitude).
        Strong jet stream over the observer location degrades astronomical seeing.

        Args:
            lat: Latitude
            lon: Longitude
            time: Time for the data

        Returns:
            Wind speed in m/s at 250hPa, or None if unavailable
        """
        data = await self.get_upper_atmosphere(lat, lon, hours=24)
        if not data:
            return None

        # Find closest time
        target_ts = time.timestamp()
        closest = min(data, key=lambda d: abs(d["timestamp"].timestamp() - target_ts))
        return closest.get("wind_speed_250hpa")

    async def get_upper_atmosphere(
        self, lat: float, lon: float, hours: int = 48
    ) -> list[dict]:
        """Get upper atmosphere data.

        Args:
            lat: Latitude
            lon: Longitude
            hours: Number of hours to forecast

        Returns:
            List of dicts with upper atmosphere data
        """
        client = await self._get_client()

        # Request winds at multiple pressure levels
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": ",".join([
                "wind_speed_250hPa",  # Jet stream level
                "wind_speed_300hPa",  # Upper troposphere
                "wind_speed_500hPa",  # Mid troposphere
                "wind_speed_700hPa",  # Lower troposphere
                "wind_speed_850hPa",  # Near surface
                "geopotential_height_500hPa",  # For stability
            ]),
            "forecast_hours": min(hours, 384),
            "timezone": "UTC",
        }

        try:
            response = await client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            logger.warning(f"GFS API HTTP error: {e.response.status_code}")
            return []
        except httpx.RequestError as e:
            logger.warning(f"GFS API request error: {e}")
            return []

        return self._parse_response(data)

    def _parse_response(self, data: dict) -> list[dict]:
        """Parse the API response."""
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])

        if not times:
            return []

        result = []
        for i, time_str in enumerate(times):
            try:
                timestamp = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)

                entry = {
                    "timestamp": timestamp,
                    "wind_speed_250hpa": self._get_value(hourly, "wind_speed_250hPa", i),
                    "wind_speed_300hpa": self._get_value(hourly, "wind_speed_300hPa", i),
                    "wind_speed_500hpa": self._get_value(hourly, "wind_speed_500hPa", i),
                    "wind_speed_700hpa": self._get_value(hourly, "wind_speed_700hPa", i),
                    "wind_speed_850hpa": self._get_value(hourly, "wind_speed_850hPa", i),
                    "geopotential_500hpa": self._get_value(
                        hourly, "geopotential_height_500hPa", i
                    ),
                }
                result.append(entry)
            except (ValueError, KeyError) as e:
                logger.warning(f"Failed to parse GFS data at index {i}: {e}")
                continue

        return result

    @staticmethod
    def _get_value(
        hourly: dict, key: str, index: int, default: float | None = None
    ) -> float | None:
        """Safely get a value from the hourly data."""
        values = hourly.get(key, [])
        if index < len(values) and values[index] is not None:
            # Convert km/h to m/s for wind speeds
            value = float(values[index])
            if "wind_speed" in key:
                value = value / 3.6
            return value
        return default

    async def get_richardson_number(
        self, lat: float, lon: float, time: datetime
    ) -> float | None:
        """Estimate Richardson number for atmospheric stability.

        The Richardson number indicates atmospheric stability.
        Ri < 0.25: Turbulent (poor seeing)
        Ri > 1.0: Stable (good seeing)

        This is a simplified estimate based on available data.

        Args:
            lat: Latitude
            lon: Longitude
            time: Time for calculation

        Returns:
            Estimated Richardson number, or None if unavailable
        """
        data = await self.get_upper_atmosphere(lat, lon, hours=24)
        if not data:
            return None

        # Find closest time
        target_ts = time.timestamp()
        closest = min(data, key=lambda d: abs(d["timestamp"].timestamp() - target_ts))

        # Get wind speeds at different levels
        w850 = closest.get("wind_speed_850hpa")
        w500 = closest.get("wind_speed_500hpa")

        if w850 is None or w500 is None:
            return None

        # Simplified estimate based on wind shear
        # Higher shear = lower Richardson number = more turbulence
        wind_shear = abs(w500 - w850)

        if wind_shear < 5:
            return 2.0  # Very stable
        elif wind_shear < 10:
            return 1.0  # Stable
        elif wind_shear < 20:
            return 0.5  # Marginal
        else:
            return 0.2  # Turbulent
