"""Weather data models."""

from datetime import datetime

from pydantic import BaseModel, Field


class WeatherData(BaseModel):
    """Weather conditions at a specific time and location."""

    timestamp: datetime = Field(description="Time of the observation/forecast")

    # Temperature
    temperature: float = Field(description="Surface temperature in Celsius")
    temperature_850hpa: float | None = Field(
        default=None, description="Temperature at 850hPa (~1500m) in Celsius"
    )
    dew_point: float = Field(description="Dew point temperature in Celsius")

    # Wind
    wind_speed_10m: float = Field(description="Wind speed at 10m in m/s")
    wind_speed_80m: float | None = Field(
        default=None, description="Wind speed at 80m in m/s"
    )
    wind_gusts: float = Field(description="Wind gusts in m/s")
    wind_direction: float = Field(description="Wind direction in degrees (0-360)")

    # Humidity and clouds
    humidity: float = Field(ge=0, le=100, description="Relative humidity 0-100%")
    cloud_cover: float = Field(ge=0, le=100, description="Total cloud cover 0-100%")
    cloud_cover_low: float | None = Field(
        default=None, ge=0, le=100, description="Low cloud cover 0-100%"
    )
    cloud_cover_mid: float | None = Field(
        default=None, ge=0, le=100, description="Mid cloud cover 0-100%"
    )
    cloud_cover_high: float | None = Field(
        default=None, ge=0, le=100, description="High cloud cover 0-100%"
    )

    # Pressure
    pressure: float = Field(description="Surface pressure in hPa")

    # Upper atmosphere (for jet stream / seeing)
    jet_stream_speed: float | None = Field(
        default=None, description="Wind speed at 250hPa (jet stream level) in m/s"
    )

    # Precipitation
    precipitation: float = Field(default=0, description="Precipitation in mm")
    precipitation_probability: float | None = Field(
        default=None, ge=0, le=100, description="Precipitation probability 0-100%"
    )

    # Visibility
    visibility: float | None = Field(default=None, description="Visibility in meters")

    @property
    def temperature_differential(self) -> float:
        """Temperature difference from dew point (higher = drier air)."""
        return self.temperature - self.dew_point

    @property
    def is_dry(self) -> bool:
        """Check if air is relatively dry (good for seeing)."""
        return self.temperature_differential > 5

    @property
    def wind_shear(self) -> float | None:
        """Wind shear between 10m and 80m (if available)."""
        if self.wind_speed_80m is not None:
            return abs(self.wind_speed_80m - self.wind_speed_10m)
        return None

    def model_dump_json_safe(self) -> dict:
        """Dump model with datetime as ISO string for JSON serialization."""
        data = self.model_dump()
        data["timestamp"] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_json_safe(cls, data: dict) -> "WeatherData":
        """Create model from JSON-safe dict with ISO datetime string."""
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


class WeatherForecast(BaseModel):
    """Collection of weather data points for a forecast period."""

    location_name: str
    latitude: float
    longitude: float
    timezone: str
    hourly: list[WeatherData]

    def get_at_time(self, target_time: datetime) -> WeatherData | None:
        """Get weather data closest to a target time."""
        if not self.hourly:
            return None

        closest = min(
            self.hourly,
            key=lambda w: abs((w.timestamp - target_time).total_seconds()),
        )
        return closest
