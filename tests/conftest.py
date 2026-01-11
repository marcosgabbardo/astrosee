"""Pytest fixtures for Astrosee tests."""

from datetime import datetime, timezone

import pytest

from astrosee.astronomy.models import Location, CelestialObject, ObjectType
from astrosee.weather.models import WeatherData
from astrosee.scoring.models import SeeingScore


@pytest.fixture
def sample_location() -> Location:
    """Sample observer location (Criciuma, SC, Brazil)."""
    return Location(
        name="Test Observatory",
        latitude=-29.18,
        longitude=-49.64,
        elevation=50,
        timezone="America/Sao_Paulo",
    )


@pytest.fixture
def sample_weather() -> WeatherData:
    """Sample weather data with good conditions."""
    return WeatherData(
        timestamp=datetime.now(timezone.utc),
        temperature=18.5,
        temperature_850hpa=12.0,
        dew_point=10.0,
        wind_speed_10m=2.5,
        wind_speed_80m=4.0,
        wind_gusts=4.5,
        wind_direction=180,
        humidity=55,
        cloud_cover=15,
        cloud_cover_low=5,
        cloud_cover_mid=5,
        cloud_cover_high=10,
        pressure=1018,
        jet_stream_speed=25,
        precipitation=0,
        precipitation_probability=5,
    )


@pytest.fixture
def poor_weather() -> WeatherData:
    """Sample weather data with poor conditions."""
    return WeatherData(
        timestamp=datetime.now(timezone.utc),
        temperature=15.0,
        temperature_850hpa=14.0,
        dew_point=14.0,
        wind_speed_10m=8.0,
        wind_speed_80m=15.0,
        wind_gusts=18.0,
        wind_direction=270,
        humidity=95,
        cloud_cover=85,
        cloud_cover_low=70,
        cloud_cover_mid=50,
        cloud_cover_high=30,
        pressure=1005,
        jet_stream_speed=65,
        precipitation=0.5,
        precipitation_probability=80,
    )


@pytest.fixture
def sample_planet() -> CelestialObject:
    """Sample planet (Jupiter)."""
    return CelestialObject(
        name="Jupiter",
        designation="Jupiter",
        ra=0,
        dec=0,
        magnitude=-2.9,
        object_type=ObjectType.PLANET,
        description="Gas giant",
    )


@pytest.fixture
def sample_deep_sky() -> CelestialObject:
    """Sample deep-sky object (M42)."""
    return CelestialObject(
        name="Orion Nebula",
        designation="M42",
        ra=83.82,
        dec=-5.39,
        magnitude=4.0,
        object_type=ObjectType.NEBULA,
        constellation="Orion",
        size="85x60 arcmin",
        description="Bright emission nebula",
        aliases=["NGC 1976", "Great Orion Nebula"],
    )
