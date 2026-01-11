"""Astronomy calculations using Skyfield."""

import logging
import math
from datetime import datetime, timezone
from pathlib import Path

from skyfield import almanac
from skyfield.api import N, S, E, W, load, wgs84
from skyfield.timelib import Time

from astrosee.astronomy.models import AstronomyData, CelestialObject, Location, TargetPosition

logger = logging.getLogger(__name__)


class AstronomyCalculator:
    """Calculator for astronomical data using Skyfield."""

    def __init__(self, data_dir: Path | None = None):
        """Initialize the calculator.

        Args:
            data_dir: Directory to store ephemeris files (default: ~/.astrosee/data)
        """
        self.data_dir = data_dir or Path.home() / ".astrosee" / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Initialize timescale
        self.ts = load.timescale()

        # Load ephemeris (DE421 is smaller, good enough for our purposes)
        self._ephemeris = None
        self._sun = None
        self._moon = None
        self._earth = None
        self._planets = {}

    def _load_ephemeris(self):
        """Lazily load the ephemeris data."""
        if self._ephemeris is None:
            ephemeris_path = self.data_dir / "de421.bsp"
            load.directory = str(self.data_dir)
            self._ephemeris = load("de421.bsp")
            self._sun = self._ephemeris["sun"]
            self._moon = self._ephemeris["moon"]
            self._earth = self._ephemeris["earth"]

            # Load planets
            self._planets = {
                "mercury": self._ephemeris["mercury"],
                "venus": self._ephemeris["venus"],
                "mars": self._ephemeris["mars"],
                "jupiter": self._ephemeris["jupiter barycenter"],
                "saturn": self._ephemeris["saturn barycenter"],
                "uranus": self._ephemeris["uranus barycenter"],
                "neptune": self._ephemeris["neptune barycenter"],
            }

    def _get_observer(self, location: Location) -> wgs84:
        """Get a Skyfield observer from a Location."""
        return wgs84.latlon(
            location.latitude,
            location.longitude,
            elevation_m=location.elevation,
        )

    def _datetime_to_skyfield(self, dt: datetime) -> Time:
        """Convert datetime to Skyfield Time."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return self.ts.from_datetime(dt)

    def get_moon_illumination(self, time: datetime) -> float:
        """Get Moon illumination percentage.

        Args:
            time: Time for calculation

        Returns:
            Illumination percentage (0-100)
        """
        self._load_ephemeris()
        t = self._datetime_to_skyfield(time)

        # Calculate phase angle
        sun_pos = self._earth.at(t).observe(self._sun).apparent()
        moon_pos = self._earth.at(t).observe(self._moon).apparent()

        _, sun_lon, _ = sun_pos.ecliptic_latlon()
        _, moon_lon, _ = moon_pos.ecliptic_latlon()

        phase_angle = (moon_lon.degrees - sun_lon.degrees) % 360

        # Convert phase angle to illumination
        illumination = (1 - math.cos(math.radians(phase_angle))) / 2 * 100

        return illumination

    def get_moon_phase_name(self, illumination: float) -> str:
        """Get human-readable moon phase name.

        Args:
            illumination: Moon illumination percentage (0-100)

        Returns:
            Phase name
        """
        if illumination < 3:
            return "New Moon"
        elif illumination < 25:
            return "Waxing Crescent"
        elif illumination < 50:
            return "First Quarter"
        elif illumination < 75:
            return "Waxing Gibbous"
        elif illumination < 97:
            return "Full Moon" if illumination > 95 else "Waning Gibbous"
        else:
            return "Full Moon"

    def get_altitude_azimuth(
        self,
        ra: float,
        dec: float,
        location: Location,
        time: datetime,
    ) -> tuple[float, float]:
        """Calculate altitude and azimuth for celestial coordinates.

        Args:
            ra: Right ascension in degrees
            dec: Declination in degrees
            location: Observer location
            time: Time of observation

        Returns:
            Tuple of (altitude, azimuth) in degrees
        """
        self._load_ephemeris()
        t = self._datetime_to_skyfield(time)
        observer = self._get_observer(location)

        # Create a Star object for distant objects (deep sky, stars)
        from skyfield.api import Star

        ra_hours = ra / 15  # Convert degrees to hours
        star = Star(ra_hours=ra_hours, dec_degrees=dec)

        # Calculate apparent position from observer
        earth_observer = self._earth + observer
        apparent = earth_observer.at(t).observe(star).apparent()
        alt, az, _ = apparent.altaz()

        return alt.degrees, az.degrees

    def get_airmass(self, altitude: float) -> float:
        """Calculate atmospheric airmass.

        Uses the Pickering (2002) formula which is accurate to ~90% down to
        the horizon.

        Args:
            altitude: Object altitude in degrees

        Returns:
            Airmass value (1.0 at zenith, higher near horizon)
        """
        if altitude <= 0:
            return float("inf")

        # Pickering (2002) formula
        alt_rad = math.radians(altitude)
        arg = altitude + 244 / (165 + 47 * altitude**1.1)
        airmass = 1 / math.sin(math.radians(arg))

        return max(1.0, airmass)

    def get_sun_altitude(self, location: Location, time: datetime) -> float:
        """Get Sun altitude.

        Args:
            location: Observer location
            time: Time of observation

        Returns:
            Sun altitude in degrees (negative = below horizon)
        """
        self._load_ephemeris()
        t = self._datetime_to_skyfield(time)
        observer = self._get_observer(location)

        earth_observer = self._earth + observer
        sun_apparent = earth_observer.at(t).observe(self._sun).apparent()
        alt, _, _ = sun_apparent.altaz()

        return alt.degrees

    def get_moon_position(
        self, location: Location, time: datetime
    ) -> tuple[float, float]:
        """Get Moon altitude and azimuth.

        Args:
            location: Observer location
            time: Time of observation

        Returns:
            Tuple of (altitude, azimuth) in degrees
        """
        self._load_ephemeris()
        t = self._datetime_to_skyfield(time)
        observer = self._get_observer(location)

        earth_observer = self._earth + observer
        moon_apparent = earth_observer.at(t).observe(self._moon).apparent()
        alt, az, _ = moon_apparent.altaz()

        return alt.degrees, az.degrees

    def get_planet_position(
        self, planet_name: str, location: Location, time: datetime
    ) -> tuple[float, float] | None:
        """Get planet altitude and azimuth.

        Args:
            planet_name: Planet name (lowercase)
            location: Observer location
            time: Time of observation

        Returns:
            Tuple of (altitude, azimuth) or None if planet not found
        """
        self._load_ephemeris()
        planet_name = planet_name.lower()

        if planet_name not in self._planets:
            return None

        t = self._datetime_to_skyfield(time)
        observer = self._get_observer(location)

        earth_observer = self._earth + observer
        planet_apparent = earth_observer.at(t).observe(self._planets[planet_name]).apparent()
        alt, az, _ = planet_apparent.altaz()

        return alt.degrees, az.degrees

    def get_astronomy_data(
        self, location: Location, time: datetime
    ) -> AstronomyData:
        """Get comprehensive astronomy data for a location and time.

        Args:
            location: Observer location
            time: Time for calculations

        Returns:
            AstronomyData with all astronomical information
        """
        self._load_ephemeris()

        # Moon data
        moon_illumination = self.get_moon_illumination(time)
        moon_alt, moon_az = self.get_moon_position(location, time)
        moon_phase = self.get_moon_phase_name(moon_illumination)

        # Sun data
        sun_alt = self.get_sun_altitude(location, time)

        return AstronomyData(
            moon_illumination=moon_illumination,
            moon_altitude=moon_alt,
            moon_azimuth=moon_az,
            moon_phase=moon_phase,
            sun_altitude=sun_alt,
        )

    def get_target_position(
        self,
        obj: CelestialObject,
        location: Location,
        time: datetime,
    ) -> TargetPosition:
        """Get position information for a celestial object.

        Args:
            obj: Celestial object
            location: Observer location
            time: Time for calculations

        Returns:
            TargetPosition with altitude, azimuth, airmass
        """
        # Check if it's the Moon (needs special handling)
        if obj.object_type.value == "moon" or obj.name.lower() == "moon":
            alt, az = self.get_moon_position(location, time)
        # Check if it's a planet
        elif obj.object_type.value == "planet":
            planet_pos = self.get_planet_position(obj.name.lower(), location, time)
            if planet_pos:
                alt, az = planet_pos
            else:
                # Fall back to catalog coordinates
                alt, az = self.get_altitude_azimuth(obj.ra, obj.dec, location, time)
        else:
            alt, az = self.get_altitude_azimuth(obj.ra, obj.dec, location, time)

        airmass = self.get_airmass(alt)
        is_visible = alt > 0

        return TargetPosition(
            object=obj,
            altitude=alt,
            azimuth=az,
            airmass=airmass,
            is_visible=is_visible,
        )

    def is_astronomical_night(self, location: Location, time: datetime) -> bool:
        """Check if it's astronomical night (sun below -18 degrees).

        Args:
            location: Observer location
            time: Time to check

        Returns:
            True if it's astronomical night
        """
        sun_alt = self.get_sun_altitude(location, time)
        return sun_alt < -18
