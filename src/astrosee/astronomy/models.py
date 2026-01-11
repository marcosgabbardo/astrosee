"""Astronomy data models."""

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class ObjectType(str, Enum):
    """Type of celestial object."""

    PLANET = "planet"
    MOON = "moon"
    GALAXY = "galaxy"
    NEBULA = "nebula"
    OPEN_CLUSTER = "open_cluster"
    GLOBULAR_CLUSTER = "globular_cluster"
    PLANETARY_NEBULA = "planetary_nebula"
    SUPERNOVA_REMNANT = "supernova_remnant"
    STAR = "star"
    DOUBLE_STAR = "double_star"
    ASTEROID = "asteroid"
    COMET = "comet"
    OTHER = "other"


class Location(BaseModel):
    """Observer location on Earth."""

    name: str = Field(description="Location name")
    latitude: float = Field(ge=-90, le=90, description="Latitude in degrees")
    longitude: float = Field(ge=-180, le=180, description="Longitude in degrees")
    elevation: float = Field(default=0, ge=0, description="Elevation in meters")
    timezone: str = Field(default="UTC", description="Timezone name")

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        if not -90 <= v <= 90:
            raise ValueError("Latitude must be between -90 and 90")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        if not -180 <= v <= 180:
            raise ValueError("Longitude must be between -180 and 180")
        return v

    def __str__(self) -> str:
        lat_dir = "N" if self.latitude >= 0 else "S"
        lon_dir = "E" if self.longitude >= 0 else "W"
        return (
            f"{self.name} ({abs(self.latitude):.2f}{lat_dir}, "
            f"{abs(self.longitude):.2f}{lon_dir})"
        )


class CelestialObject(BaseModel):
    """A celestial object in the catalog."""

    name: str = Field(description="Common name")
    designation: str = Field(description="Catalog designation (e.g., M31, NGC224)")
    ra: float = Field(ge=0, lt=360, description="Right ascension in degrees")
    dec: float = Field(ge=-90, le=90, description="Declination in degrees")
    magnitude: float | None = Field(default=None, description="Apparent magnitude")
    object_type: ObjectType = Field(description="Type of object")
    constellation: str | None = Field(default=None, description="Constellation")
    size: str | None = Field(default=None, description="Angular size")
    description: str | None = Field(default=None, description="Brief description")
    aliases: list[str] = Field(default_factory=list, description="Alternative names")

    @property
    def is_deep_sky(self) -> bool:
        """Check if this is a deep-sky object (affected by light pollution/moon)."""
        return self.object_type in {
            ObjectType.GALAXY,
            ObjectType.NEBULA,
            ObjectType.OPEN_CLUSTER,
            ObjectType.GLOBULAR_CLUSTER,
            ObjectType.PLANETARY_NEBULA,
            ObjectType.SUPERNOVA_REMNANT,
        }

    @property
    def is_solar_system(self) -> bool:
        """Check if this is a solar system object."""
        return self.object_type in {
            ObjectType.PLANET,
            ObjectType.MOON,
            ObjectType.ASTEROID,
            ObjectType.COMET,
        }

    def matches_search(self, query: str) -> bool:
        """Check if object matches a search query."""
        query_lower = query.lower().strip()
        if query_lower in self.name.lower():
            return True
        if query_lower in self.designation.lower():
            return True
        for alias in self.aliases:
            if query_lower in alias.lower():
                return True
        return False


class AstronomyData(BaseModel):
    """Astronomical data for a specific time and location."""

    # Moon
    moon_illumination: float = Field(
        ge=0, le=100, description="Moon illumination percentage"
    )
    moon_altitude: float = Field(description="Moon altitude in degrees")
    moon_azimuth: float = Field(description="Moon azimuth in degrees")
    moon_phase: str = Field(description="Moon phase name")
    moon_rise: str | None = Field(default=None, description="Moon rise time")
    moon_set: str | None = Field(default=None, description="Moon set time")

    # Sun
    sun_altitude: float = Field(description="Sun altitude in degrees")
    sunrise: str | None = Field(default=None, description="Sunrise time")
    sunset: str | None = Field(default=None, description="Sunset time")
    astronomical_twilight_end: str | None = Field(
        default=None, description="End of astronomical twilight"
    )
    astronomical_twilight_begin: str | None = Field(
        default=None, description="Begin of astronomical twilight"
    )

    @property
    def is_astronomical_night(self) -> bool:
        """Check if it's currently astronomical night (sun < -18 degrees)."""
        return self.sun_altitude < -18

    @property
    def is_moon_up(self) -> bool:
        """Check if moon is above horizon."""
        return self.moon_altitude > 0


class TargetPosition(BaseModel):
    """Position of a target object in the sky."""

    object: CelestialObject
    altitude: float = Field(description="Altitude above horizon in degrees")
    azimuth: float = Field(description="Azimuth in degrees (0=N, 90=E)")
    airmass: float = Field(description="Atmospheric airmass")
    is_visible: bool = Field(description="Whether object is above horizon")
    rise_time: str | None = Field(default=None, description="Rise time")
    set_time: str | None = Field(default=None, description="Set time")
    transit_time: str | None = Field(default=None, description="Transit time")
    transit_altitude: float | None = Field(
        default=None, description="Altitude at transit"
    )

    @property
    def is_well_placed(self) -> bool:
        """Check if object is well-placed for observation (altitude > 30)."""
        return self.altitude > 30

    @property
    def airmass_quality(self) -> str:
        """Get a quality rating based on airmass."""
        if self.airmass <= 1.2:
            return "Excellent"
        elif self.airmass <= 1.5:
            return "Good"
        elif self.airmass <= 2.0:
            return "Fair"
        elif self.airmass <= 3.0:
            return "Poor"
        else:
            return "Very poor"
