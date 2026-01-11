"""Configuration management using TOML."""

import sys
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

import tomli_w

from astrosee.astronomy.models import Location
from astrosee.core.exceptions import ConfigError


class ConfigManager:
    """Manages user configuration stored in ~/.astrosee/."""

    DEFAULT_DIR = Path.home() / ".astrosee"
    CONFIG_FILENAME = "config.toml"

    def __init__(self, config_dir: Path | None = None):
        """Initialize config manager.

        Args:
            config_dir: Custom config directory (default: ~/.astrosee/)
        """
        self.config_dir = config_dir or self.DEFAULT_DIR
        self.config_file = self.config_dir / self.CONFIG_FILENAME
        self._config: dict[str, Any] = {}
        self._ensure_config_exists()
        self._load_config()

    def _ensure_config_exists(self) -> None:
        """Create config directory and default config if needed."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.config_file.exists():
            default_config = {
                "settings": {
                    "cache_ttl_hours": 1,
                    "default_forecast_hours": 48,
                    "units": "metric",
                },
                "locations": {},
            }
            self._write_config(default_config)

    def _load_config(self) -> None:
        """Load configuration from file."""
        try:
            with open(self.config_file, "rb") as f:
                self._config = tomllib.load(f)
        except Exception as e:
            raise ConfigError(f"Failed to load config: {e}") from e

    def _write_config(self, config: dict[str, Any] | None = None) -> None:
        """Write configuration to file."""
        if config is not None:
            self._config = config
        try:
            with open(self.config_file, "wb") as f:
                tomli_w.dump(self._config, f)
        except Exception as e:
            raise ConfigError(f"Failed to write config: {e}") from e

    def _save(self) -> None:
        """Save current config to file."""
        self._write_config()

    # Settings
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return self._config.get("settings", {}).get(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        """Set a setting value."""
        if "settings" not in self._config:
            self._config["settings"] = {}
        self._config["settings"][key] = value
        self._save()

    @property
    def cache_ttl_hours(self) -> int:
        """Get cache TTL in hours."""
        return self.get_setting("cache_ttl_hours", 1)

    @property
    def default_forecast_hours(self) -> int:
        """Get default forecast duration in hours."""
        return self.get_setting("default_forecast_hours", 48)

    # Locations
    def get_default_location(self) -> Location | None:
        """Get the default location."""
        default_name = self._config.get("default_location")
        if default_name and default_name in self._config.get("locations", {}):
            return self.get_location(default_name)
        # Return first location if no default set
        locations = self._config.get("locations", {})
        if locations:
            first_name = next(iter(locations))
            return self.get_location(first_name)
        return None

    def set_default_location(self, name: str) -> None:
        """Set the default location by name."""
        if name not in self._config.get("locations", {}):
            raise ConfigError(f"Location '{name}' not found")
        self._config["default_location"] = name
        self._save()

    def get_location(self, name: str) -> Location | None:
        """Get a location by name."""
        locations = self._config.get("locations", {})
        if name not in locations:
            return None
        loc_data = locations[name]
        return Location(
            name=name,
            latitude=loc_data["latitude"],
            longitude=loc_data["longitude"],
            elevation=loc_data.get("elevation", 0),
            timezone=loc_data.get("timezone", "UTC"),
        )

    def get_all_locations(self) -> dict[str, Location]:
        """Get all saved locations."""
        result = {}
        for name in self._config.get("locations", {}):
            loc = self.get_location(name)
            if loc:
                result[name] = loc
        return result

    def add_location(
        self,
        name: str,
        latitude: float,
        longitude: float,
        elevation: float = 0,
        timezone: str = "UTC",
        set_default: bool = False,
    ) -> Location:
        """Add a new location.

        Args:
            name: Location name
            latitude: Latitude in degrees
            longitude: Longitude in degrees
            elevation: Elevation in meters
            timezone: Timezone name
            set_default: Whether to set this as the default location

        Returns:
            The created Location object
        """
        if "locations" not in self._config:
            self._config["locations"] = {}

        self._config["locations"][name] = {
            "latitude": latitude,
            "longitude": longitude,
            "elevation": elevation,
            "timezone": timezone,
        }

        if set_default or not self._config.get("default_location"):
            self._config["default_location"] = name

        self._save()

        return Location(
            name=name,
            latitude=latitude,
            longitude=longitude,
            elevation=elevation,
            timezone=timezone,
        )

    def remove_location(self, name: str) -> bool:
        """Remove a location by name.

        Returns:
            True if location was removed, False if it didn't exist
        """
        if name not in self._config.get("locations", {}):
            return False

        del self._config["locations"][name]

        # Clear default if it was the removed location
        if self._config.get("default_location") == name:
            locations = self._config.get("locations", {})
            if locations:
                self._config["default_location"] = next(iter(locations))
            else:
                self._config.pop("default_location", None)

        self._save()
        return True

    # Alerts
    def get_alerts(self) -> list[dict[str, Any]]:
        """Get all configured alerts."""
        return self._config.get("alerts", [])

    def add_alert(self, condition: str, enabled: bool = True) -> None:
        """Add a new alert condition."""
        if "alerts" not in self._config:
            self._config["alerts"] = []
        self._config["alerts"].append({
            "condition": condition,
            "enabled": enabled,
        })
        self._save()

    def remove_alert(self, index: int) -> bool:
        """Remove an alert by index."""
        alerts = self._config.get("alerts", [])
        if 0 <= index < len(alerts):
            alerts.pop(index)
            self._save()
            return True
        return False

    @property
    def data_dir(self) -> Path:
        """Get the data directory for cache, logs, etc."""
        data_dir = self.config_dir / "data"
        data_dir.mkdir(exist_ok=True)
        return data_dir

    @property
    def cache_db_path(self) -> Path:
        """Get the path to the cache database."""
        return self.data_dir / "cache.db"
