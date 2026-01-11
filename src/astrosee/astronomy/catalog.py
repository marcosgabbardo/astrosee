"""Celestial object catalog."""

import json
import logging
from datetime import datetime
from importlib import resources
from pathlib import Path

from astrosee.astronomy.models import CelestialObject, Location, ObjectType
from astrosee.core.exceptions import CatalogNotFoundError

logger = logging.getLogger(__name__)


class CelestialCatalog:
    """Catalog of celestial objects for observation planning."""

    def __init__(self, catalog_path: Path | None = None):
        """Initialize the catalog.

        Args:
            catalog_path: Path to custom catalog JSON (default: built-in catalog)
        """
        self._objects: list[CelestialObject] = []
        self._load_catalog(catalog_path)

    def _load_catalog(self, catalog_path: Path | None = None) -> None:
        """Load objects from catalog file."""
        if catalog_path and catalog_path.exists():
            with open(catalog_path) as f:
                data = json.load(f)
        else:
            # Load built-in catalog
            try:
                catalog_file = (
                    Path(__file__).parent / "data" / "catalog.json"
                )
                with open(catalog_file) as f:
                    data = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load built-in catalog: {e}")
                data = {"objects": []}

        for obj_data in data.get("objects", []):
            try:
                obj = CelestialObject(
                    name=obj_data["name"],
                    designation=obj_data["designation"],
                    ra=obj_data.get("ra", 0),
                    dec=obj_data.get("dec", 0),
                    magnitude=obj_data.get("magnitude"),
                    object_type=ObjectType(obj_data.get("object_type", "other")),
                    constellation=obj_data.get("constellation"),
                    size=obj_data.get("size"),
                    description=obj_data.get("description"),
                    aliases=obj_data.get("aliases", []),
                )
                self._objects.append(obj)
            except Exception as e:
                logger.warning(f"Failed to load object {obj_data.get('name')}: {e}")

    def search(self, query: str) -> CelestialObject | None:
        """Search for an object by name or designation.

        Args:
            query: Search query (name, designation, or alias)

        Returns:
            Matching object or None
        """
        query_lower = query.lower().strip()

        # Exact match first
        for obj in self._objects:
            if obj.name.lower() == query_lower:
                return obj
            if obj.designation.lower() == query_lower:
                return obj

        # Partial match
        for obj in self._objects:
            if obj.matches_search(query):
                return obj

        return None

    def get(self, query: str) -> CelestialObject:
        """Get an object by name or raise error.

        Args:
            query: Search query

        Returns:
            Matching object

        Raises:
            CatalogNotFoundError: If object not found
        """
        obj = self.search(query)
        if obj is None:
            raise CatalogNotFoundError(query)
        return obj

    def search_all(self, query: str) -> list[CelestialObject]:
        """Search for all matching objects.

        Args:
            query: Search query

        Returns:
            List of matching objects
        """
        query_lower = query.lower().strip()
        matches = []

        for obj in self._objects:
            if obj.matches_search(query):
                matches.append(obj)

        return matches

    def get_by_type(self, object_type: ObjectType) -> list[CelestialObject]:
        """Get all objects of a specific type.

        Args:
            object_type: Type to filter by

        Returns:
            List of matching objects
        """
        return [obj for obj in self._objects if obj.object_type == object_type]

    def get_planets(self) -> list[CelestialObject]:
        """Get all planets."""
        return self.get_by_type(ObjectType.PLANET)

    def get_deep_sky(self) -> list[CelestialObject]:
        """Get all deep-sky objects."""
        return [obj for obj in self._objects if obj.is_deep_sky]

    def get_by_constellation(self, constellation: str) -> list[CelestialObject]:
        """Get objects in a constellation.

        Args:
            constellation: Constellation name

        Returns:
            List of objects in that constellation
        """
        const_lower = constellation.lower()
        return [
            obj for obj in self._objects
            if obj.constellation and obj.constellation.lower() == const_lower
        ]

    def get_by_magnitude(
        self, max_magnitude: float, min_magnitude: float = -30
    ) -> list[CelestialObject]:
        """Get objects within a magnitude range.

        Args:
            max_magnitude: Maximum (faintest) magnitude
            min_magnitude: Minimum (brightest) magnitude

        Returns:
            List of objects within range
        """
        return [
            obj for obj in self._objects
            if obj.magnitude is not None
            and min_magnitude <= obj.magnitude <= max_magnitude
        ]

    def get_visible(
        self,
        location: Location,
        time: datetime,
        min_altitude: float = 15,
        calculator: "AstronomyCalculator | None" = None,
    ) -> list[tuple[CelestialObject, float, float]]:
        """Get objects visible from a location.

        Args:
            location: Observer location
            time: Time of observation
            min_altitude: Minimum altitude in degrees
            calculator: Optional astronomy calculator (creates one if not provided)

        Returns:
            List of (object, altitude, azimuth) tuples for visible objects
        """
        if calculator is None:
            from astrosee.astronomy.calculator import AstronomyCalculator
            calculator = AstronomyCalculator()

        visible = []
        for obj in self._objects:
            # Skip planets (need different calculation)
            if obj.is_solar_system:
                continue

            alt, az = calculator.get_altitude_azimuth(
                obj.ra, obj.dec, location, time
            )
            if alt >= min_altitude:
                visible.append((obj, alt, az))

        # Sort by altitude (highest first)
        return sorted(visible, key=lambda x: x[1], reverse=True)

    @property
    def all_objects(self) -> list[CelestialObject]:
        """Get all objects in the catalog."""
        return self._objects.copy()

    def __len__(self) -> int:
        return len(self._objects)

    def __iter__(self):
        return iter(self._objects)
