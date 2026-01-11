"""CLI context management."""

from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from astrosee.astronomy.calculator import AstronomyCalculator
from astrosee.astronomy.catalog import CelestialCatalog
from astrosee.display.renderer import DisplayRenderer
from astrosee.scoring.engine import ScoringEngine
from astrosee.services.forecast import ForecastService
from astrosee.services.seeing import SeeingService
from astrosee.storage.cache import CacheManager
from astrosee.storage.config import ConfigManager
from astrosee.weather.noaa_gfs import NoaaGfsClient
from astrosee.weather.openmeteo import OpenMeteoClient


@dataclass
class CliContext:
    """Context object passed to all CLI commands."""

    config: ConfigManager
    console: Console
    renderer: DisplayRenderer
    verbose: bool = False

    # Lazily initialized services
    _seeing_service: SeeingService | None = None
    _forecast_service: ForecastService | None = None
    _cache: CacheManager | None = None

    @classmethod
    def create(
        cls,
        config_dir: Path | None = None,
        verbose: bool = False,
    ) -> "CliContext":
        """Create a new CLI context.

        Args:
            config_dir: Custom config directory
            verbose: Enable verbose output

        Returns:
            Initialized CliContext
        """
        config = ConfigManager(config_dir)
        console = Console()
        renderer = DisplayRenderer(console)

        return cls(
            config=config,
            console=console,
            renderer=renderer,
            verbose=verbose,
        )

    def get_cache(self) -> CacheManager:
        """Get or create cache manager."""
        if self._cache is None:
            self._cache = CacheManager(self.config.cache_db_path)
        return self._cache

    def get_seeing_service(self) -> SeeingService:
        """Get or create seeing service."""
        if self._seeing_service is None:
            self._seeing_service = SeeingService(
                cache_manager=self.get_cache(),
                weather_client=OpenMeteoClient(),
                gfs_client=NoaaGfsClient(),
                astronomy_calculator=AstronomyCalculator(self.config.data_dir),
                catalog=CelestialCatalog(),
                scoring_engine=ScoringEngine(),
                cache_ttl_hours=self.config.cache_ttl_hours,
            )
        return self._seeing_service

    def get_forecast_service(self) -> ForecastService:
        """Get or create forecast service."""
        if self._forecast_service is None:
            self._forecast_service = ForecastService(self.get_seeing_service())
        return self._forecast_service

    async def cleanup(self) -> None:
        """Clean up resources."""
        if self._seeing_service:
            await self._seeing_service.close()
        if self._cache:
            await self._cache.close()
