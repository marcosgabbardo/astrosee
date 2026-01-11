"""Main seeing service - orchestrates weather, astronomy, and scoring."""

import logging
from datetime import datetime, timedelta, timezone

from astrosee.astronomy.calculator import AstronomyCalculator
from astrosee.astronomy.catalog import CelestialCatalog
from astrosee.astronomy.models import CelestialObject, Location
from astrosee.core.exceptions import WeatherAPIError
from astrosee.scoring.engine import ScoringEngine
from astrosee.scoring.models import SeeingForecast, SeeingReport
from astrosee.storage.cache import CacheManager
from astrosee.weather.models import WeatherData
from astrosee.weather.noaa_gfs import NoaaGfsClient
from astrosee.weather.openmeteo import OpenMeteoClient

logger = logging.getLogger(__name__)


class SeeingService:
    """Main service for seeing predictions.

    Orchestrates weather data fetching, astronomical calculations,
    and score computation with caching for performance.
    """

    def __init__(
        self,
        cache_manager: CacheManager | None = None,
        weather_client: OpenMeteoClient | None = None,
        gfs_client: NoaaGfsClient | None = None,
        astronomy_calculator: AstronomyCalculator | None = None,
        catalog: CelestialCatalog | None = None,
        scoring_engine: ScoringEngine | None = None,
        cache_ttl_hours: int = 1,
    ):
        """Initialize the seeing service.

        Args:
            cache_manager: Cache for API responses
            weather_client: Weather API client
            gfs_client: NOAA GFS client for jet stream
            astronomy_calculator: Astronomical calculator
            catalog: Celestial object catalog
            scoring_engine: Scoring engine
            cache_ttl_hours: Cache TTL in hours
        """
        self.cache = cache_manager
        self.weather_client = weather_client or OpenMeteoClient()
        self.gfs_client = gfs_client or NoaaGfsClient()
        self.astronomy = astronomy_calculator or AstronomyCalculator()
        self.catalog = catalog or CelestialCatalog()
        self.scoring = scoring_engine or ScoringEngine()
        self.cache_ttl = cache_ttl_hours

    async def close(self) -> None:
        """Close all clients."""
        await self.weather_client.close()
        await self.gfs_client.close()
        if self.cache:
            await self.cache.close()

    async def get_current_conditions(
        self,
        location: Location,
        target: CelestialObject | str | None = None,
    ) -> SeeingReport:
        """Get current seeing conditions.

        Args:
            location: Observer location
            target: Optional target object (name string or CelestialObject)

        Returns:
            SeeingReport with current conditions
        """
        now = datetime.now(timezone.utc)

        # Resolve target if string
        target_obj = None
        if isinstance(target, str):
            target_obj = self.catalog.search(target)
        elif isinstance(target, CelestialObject):
            target_obj = target

        # Get weather data (with caching)
        weather = await self._get_weather(location, now)

        # Get jet stream data (best effort)
        try:
            jet_speed = await self.gfs_client.get_jet_stream_speed(
                location.latitude, location.longitude, now
            )
            if jet_speed is not None:
                weather = weather.model_copy(update={"jet_stream_speed": jet_speed})
        except Exception as e:
            logger.debug(f"Failed to get jet stream data: {e}")

        # Get astronomy data
        astronomy_data = self.astronomy.get_astronomy_data(location, now)

        # Get target position if specified
        target_position = None
        airmass = None
        is_deep_sky = False

        if target_obj:
            target_position = self.astronomy.get_target_position(
                target_obj, location, now
            )
            airmass = target_position.airmass
            is_deep_sky = target_obj.is_deep_sky

        # Calculate score
        score = self.scoring.calculate_score(
            weather,
            moon_illumination=astronomy_data.moon_illumination,
            moon_altitude=astronomy_data.moon_altitude,
            airmass=airmass,
            is_deep_sky=is_deep_sky,
        )

        return SeeingReport(
            location=location,
            timestamp=now,
            weather=weather,
            astronomy=astronomy_data,
            score=score,
            target=target_obj,
            target_position=target_position,
        )

    async def get_forecast(
        self,
        location: Location,
        hours: int = 48,
        target: CelestialObject | str | None = None,
    ) -> list[SeeingForecast]:
        """Get seeing forecast.

        Args:
            location: Observer location
            hours: Number of hours to forecast
            target: Optional target object

        Returns:
            List of hourly forecasts
        """
        # Resolve target
        target_obj = None
        if isinstance(target, str):
            target_obj = self.catalog.search(target)
        elif isinstance(target, CelestialObject):
            target_obj = target

        is_deep_sky = target_obj.is_deep_sky if target_obj else False

        # Get weather forecast
        weather_list = await self._get_weather_forecast(location, hours)

        forecasts = []
        for weather in weather_list:
            # Calculate astronomy data for each hour
            astronomy_data = self.astronomy.get_astronomy_data(
                location, weather.timestamp
            )

            # Get airmass if target specified
            airmass = None
            if target_obj:
                pos = self.astronomy.get_target_position(
                    target_obj, location, weather.timestamp
                )
                airmass = pos.airmass

            # Calculate score
            score = self.scoring.calculate_score(
                weather,
                moon_illumination=astronomy_data.moon_illumination,
                moon_altitude=astronomy_data.moon_altitude,
                airmass=airmass,
                is_deep_sky=is_deep_sky,
            )

            forecast = SeeingForecast(
                timestamp=weather.timestamp,
                score=score,
                weather=weather,
                moon_illumination=astronomy_data.moon_illumination,
                moon_altitude=astronomy_data.moon_altitude,
                is_night=astronomy_data.is_astronomical_night,
            )
            forecasts.append(forecast)

        return forecasts

    async def _get_weather(
        self,
        location: Location,
        time: datetime,
    ) -> WeatherData:
        """Get weather data with caching.

        Args:
            location: Location
            time: Time for weather

        Returns:
            WeatherData
        """
        lat, lon = location.latitude, location.longitude

        # Try cache first
        if self.cache:
            cached = await self.cache.get_weather(
                lat, lon, time, ttl_hours=self.cache_ttl
            )
            if cached:
                logger.debug("Using cached weather data")
                return cached

        # Fetch from API
        try:
            weather = await self.weather_client.get_current(lat, lon)

            # Cache the result
            if self.cache:
                await self.cache.set_weather(lat, lon, weather)

            return weather

        except WeatherAPIError as e:
            logger.warning(f"Weather API error: {e}")

            # Try stale cache as fallback
            if self.cache:
                stale = await self.cache.get_weather(
                    lat, lon, time, ignore_ttl=True
                )
                if stale:
                    logger.info("Using stale cached data due to API error")
                    return stale

            raise

    async def _get_weather_forecast(
        self,
        location: Location,
        hours: int,
    ) -> list[WeatherData]:
        """Get weather forecast with caching.

        Args:
            location: Location
            hours: Hours to forecast

        Returns:
            List of WeatherData
        """
        lat, lon = location.latitude, location.longitude

        # Fetch from API (caching forecast is more complex)
        try:
            forecast = await self.weather_client.get_forecast(lat, lon, hours)

            # Cache all data points
            if self.cache and forecast:
                await self.cache.set_weather_batch(lat, lon, forecast)

            return forecast

        except WeatherAPIError as e:
            logger.warning(f"Forecast API error: {e}")

            # Try to get whatever we have in cache
            if self.cache:
                now = datetime.now(timezone.utc)
                end = now + timedelta(hours=hours)
                cached = await self.cache.get_weather_range(
                    lat, lon, now, end, ttl_hours=self.cache_ttl * 2
                )
                if cached:
                    logger.info(f"Using {len(cached)} cached forecast entries")
                    return cached

            raise
