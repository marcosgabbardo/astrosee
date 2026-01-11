"""Custom exception hierarchy for Astrosee."""


class AstroseeError(Exception):
    """Base exception for all Astrosee errors."""

    pass


class ConfigError(AstroseeError):
    """Configuration-related errors."""

    pass


class WeatherAPIError(AstroseeError):
    """Weather API failures."""

    def __init__(self, message: str, source: str | None = None):
        self.source = source
        super().__init__(message)


class CatalogNotFoundError(AstroseeError):
    """Celestial object not found in catalog."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Object not found: {name}")


class InvalidLocationError(AstroseeError):
    """Invalid coordinates provided."""

    def __init__(self, lat: float | None = None, lon: float | None = None):
        self.lat = lat
        self.lon = lon
        message = "Invalid coordinates"
        if lat is not None:
            message += f" (latitude: {lat})"
        if lon is not None:
            message += f" (longitude: {lon})"
        super().__init__(message)


class CacheError(AstroseeError):
    """Cache read/write errors."""

    pass
