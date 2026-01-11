"""SQLite cache for API responses."""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiosqlite

from astrosee.core.exceptions import CacheError
from astrosee.weather.models import WeatherData

logger = logging.getLogger(__name__)


class CacheManager:
    """SQLite-based cache for weather and other API data."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS weather_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        timestamp TEXT NOT NULL,
        data TEXT NOT NULL,
        cached_at TEXT NOT NULL,
        source TEXT DEFAULT 'openmeteo',
        UNIQUE(latitude, longitude, timestamp, source)
    );

    CREATE INDEX IF NOT EXISTS idx_weather_coords_time
    ON weather_cache(latitude, longitude, timestamp);

    CREATE TABLE IF NOT EXISTS cache_metadata (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """

    def __init__(self, db_path: Path):
        """Initialize cache manager.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._connection: aiosqlite.Connection | None = None

    async def _get_connection(self) -> aiosqlite.Connection:
        """Get or create database connection."""
        if self._connection is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = await aiosqlite.connect(self.db_path)
            await self._init_schema()
        return self._connection

    async def _init_schema(self) -> None:
        """Initialize database schema."""
        conn = self._connection
        if conn:
            await conn.executescript(self.SCHEMA)
            await conn.commit()

    async def close(self) -> None:
        """Close the database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    def _round_coords(self, lat: float, lon: float) -> tuple[float, float]:
        """Round coordinates to 2 decimal places for cache key."""
        return (round(lat, 2), round(lon, 2))

    def _round_timestamp(self, dt: datetime) -> datetime:
        """Round timestamp to the hour for cache key."""
        return dt.replace(minute=0, second=0, microsecond=0)

    async def get_weather(
        self,
        lat: float,
        lon: float,
        timestamp: datetime,
        ttl_hours: int = 1,
        ignore_ttl: bool = False,
    ) -> WeatherData | None:
        """Get cached weather data.

        Args:
            lat: Latitude
            lon: Longitude
            timestamp: Target timestamp
            ttl_hours: Cache TTL in hours
            ignore_ttl: If True, return stale data if available

        Returns:
            Cached WeatherData or None if not found/expired
        """
        try:
            conn = await self._get_connection()
            rounded_lat, rounded_lon = self._round_coords(lat, lon)
            rounded_time = self._round_timestamp(timestamp)

            cursor = await conn.execute(
                """
                SELECT data, cached_at FROM weather_cache
                WHERE latitude = ? AND longitude = ? AND timestamp = ?
                ORDER BY cached_at DESC LIMIT 1
                """,
                (rounded_lat, rounded_lon, rounded_time.isoformat()),
            )
            row = await cursor.fetchone()

            if not row:
                return None

            data_json, cached_at_str = row
            cached_at = datetime.fromisoformat(cached_at_str)

            # Check TTL
            if not ignore_ttl:
                age = datetime.now(timezone.utc) - cached_at
                if age > timedelta(hours=ttl_hours):
                    logger.debug(f"Cache expired (age: {age})")
                    return None

            data = json.loads(data_json)
            return WeatherData.from_json_safe(data)

        except Exception as e:
            logger.warning(f"Cache read error: {e}")
            return None

    async def set_weather(
        self,
        lat: float,
        lon: float,
        weather: WeatherData,
        source: str = "openmeteo",
    ) -> None:
        """Cache weather data.

        Args:
            lat: Latitude
            lon: Longitude
            weather: Weather data to cache
            source: Data source identifier
        """
        try:
            conn = await self._get_connection()
            rounded_lat, rounded_lon = self._round_coords(lat, lon)
            rounded_time = self._round_timestamp(weather.timestamp)

            data_json = json.dumps(weather.model_dump_json_safe())
            cached_at = datetime.now(timezone.utc).isoformat()

            await conn.execute(
                """
                INSERT OR REPLACE INTO weather_cache
                (latitude, longitude, timestamp, data, cached_at, source)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    rounded_lat,
                    rounded_lon,
                    rounded_time.isoformat(),
                    data_json,
                    cached_at,
                    source,
                ),
            )
            await conn.commit()

        except Exception as e:
            logger.warning(f"Cache write error: {e}")
            raise CacheError(f"Failed to cache weather data: {e}") from e

    async def set_weather_batch(
        self,
        lat: float,
        lon: float,
        weather_list: list[WeatherData],
        source: str = "openmeteo",
    ) -> None:
        """Cache multiple weather data points.

        Args:
            lat: Latitude
            lon: Longitude
            weather_list: List of weather data to cache
            source: Data source identifier
        """
        try:
            conn = await self._get_connection()
            rounded_lat, rounded_lon = self._round_coords(lat, lon)
            cached_at = datetime.now(timezone.utc).isoformat()

            rows = []
            for weather in weather_list:
                rounded_time = self._round_timestamp(weather.timestamp)
                data_json = json.dumps(weather.model_dump_json_safe())
                rows.append((
                    rounded_lat,
                    rounded_lon,
                    rounded_time.isoformat(),
                    data_json,
                    cached_at,
                    source,
                ))

            await conn.executemany(
                """
                INSERT OR REPLACE INTO weather_cache
                (latitude, longitude, timestamp, data, cached_at, source)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            await conn.commit()

        except Exception as e:
            logger.warning(f"Cache batch write error: {e}")

    async def get_weather_range(
        self,
        lat: float,
        lon: float,
        start: datetime,
        end: datetime,
        ttl_hours: int = 1,
    ) -> list[WeatherData]:
        """Get cached weather data for a time range.

        Args:
            lat: Latitude
            lon: Longitude
            start: Start timestamp
            end: End timestamp
            ttl_hours: Cache TTL in hours

        Returns:
            List of cached WeatherData (may be incomplete)
        """
        try:
            conn = await self._get_connection()
            rounded_lat, rounded_lon = self._round_coords(lat, lon)
            cutoff = datetime.now(timezone.utc) - timedelta(hours=ttl_hours)

            cursor = await conn.execute(
                """
                SELECT data FROM weather_cache
                WHERE latitude = ? AND longitude = ?
                AND timestamp >= ? AND timestamp <= ?
                AND cached_at >= ?
                ORDER BY timestamp
                """,
                (
                    rounded_lat,
                    rounded_lon,
                    start.isoformat(),
                    end.isoformat(),
                    cutoff.isoformat(),
                ),
            )
            rows = await cursor.fetchall()

            result = []
            for (data_json,) in rows:
                data = json.loads(data_json)
                result.append(WeatherData.from_json_safe(data))

            return result

        except Exception as e:
            logger.warning(f"Cache range read error: {e}")
            return []

    async def cleanup(self, max_age_days: int = 7) -> int:
        """Remove old cache entries.

        Args:
            max_age_days: Maximum age of entries to keep

        Returns:
            Number of entries removed
        """
        try:
            conn = await self._get_connection()
            cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

            cursor = await conn.execute(
                "DELETE FROM weather_cache WHERE cached_at < ?",
                (cutoff.isoformat(),),
            )
            await conn.commit()
            return cursor.rowcount

        except Exception as e:
            logger.warning(f"Cache cleanup error: {e}")
            return 0

    async def get_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dict with cache stats
        """
        try:
            conn = await self._get_connection()

            cursor = await conn.execute("SELECT COUNT(*) FROM weather_cache")
            (total_entries,) = await cursor.fetchone()

            cursor = await conn.execute(
                "SELECT MIN(cached_at), MAX(cached_at) FROM weather_cache"
            )
            oldest, newest = await cursor.fetchone()

            return {
                "total_entries": total_entries,
                "oldest_entry": oldest,
                "newest_entry": newest,
                "db_path": str(self.db_path),
            }

        except Exception as e:
            logger.warning(f"Failed to get cache stats: {e}")
            return {"error": str(e)}
