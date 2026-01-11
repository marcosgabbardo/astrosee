"""Main rumps application for Astrosee menu bar widget."""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import rumps

from astrosee.astronomy.models import Location
from astrosee.core.exceptions import AstroseeError
from astrosee.scoring.models import SeeingReport
from astrosee.services.forecast import ForecastService
from astrosee.services.seeing import SeeingService
from astrosee.storage.cache import CacheManager
from astrosee.storage.config import ConfigManager
from astrosee.widget.menu_builder import (
    build_best_window_menu,
    build_component_scores_menu,
    build_conditions_menu,
    build_error_menu,
    build_forecast_menu,
    build_loading_menu,
)

logger = logging.getLogger(__name__)

# Default update interval in seconds (15 minutes)
DEFAULT_UPDATE_INTERVAL = 900

# Path to icon assets
ASSETS_DIR = Path(__file__).parent / "assets"
ICON_PATH = ASSETS_DIR / "icon.png"


class AstroseeWidget(rumps.App):
    """Menu bar widget for Astrosee seeing conditions."""

    def __init__(
        self,
        update_interval: int = DEFAULT_UPDATE_INTERVAL,
        config: ConfigManager | None = None,
    ):
        """Initialize the widget.

        Args:
            update_interval: Update interval in seconds
            config: ConfigManager instance (creates one if not provided)
        """
        # Load icon
        icon_path = str(ICON_PATH) if ICON_PATH.exists() else None

        super().__init__(
            name="Astrosee",
            title=None,  # No text, just icon
            icon=icon_path,
            template=True,  # Makes icon adapt to dark/light menu bar
            quit_button=None,  # We'll add our own quit button
        )

        self.update_interval = update_interval
        self.config = config or ConfigManager()
        self._location: Location | None = None
        self._last_report: SeeingReport | None = None
        self._last_error: str | None = None
        self._best_nights: list[tuple[datetime, float, str]] = []
        self._best_window: tuple[datetime | None, datetime | None, float | None] = (
            None,
            None,
            None,
        )
        self._is_updating = False

        # Build initial menu
        self._build_menu()

        # Set up timer for periodic updates (runs on main thread)
        self._timer = rumps.Timer(self._on_timer, self.update_interval)

    def _build_menu(self) -> None:
        """Build the menu structure."""
        self.menu.clear()

        # Location header
        location = self._get_location()
        if location:
            self.menu.add(rumps.MenuItem(f"\U0001F4CD {location.name}", callback=None))
        else:
            self.menu.add(rumps.MenuItem("\u26A0\uFE0F No location configured", callback=None))

        self.menu.add(None)  # Separator

        # Conditions section (placeholder or actual data)
        if self._last_error:
            for title, _ in build_error_menu(self._last_error):
                if title is None:
                    self.menu.add(None)
                else:
                    self.menu.add(rumps.MenuItem(title, callback=None))
        elif self._last_report:
            # Current conditions
            for title, _ in build_conditions_menu(self._last_report):
                if title is None:
                    self.menu.add(None)
                else:
                    self.menu.add(rumps.MenuItem(title, callback=None))

            self.menu.add(None)  # Separator

            # Component scores submenu
            components_menu = rumps.MenuItem("Component Scores")
            for title, _ in build_component_scores_menu(self._last_report):
                components_menu.add(rumps.MenuItem(title, callback=None))
            self.menu.add(components_menu)

            self.menu.add(None)  # Separator

            # Best window tonight
            for title, _ in build_best_window_menu(*self._best_window):
                if title is None:
                    self.menu.add(None)
                else:
                    self.menu.add(rumps.MenuItem(title, callback=None))

            # Forecast submenu
            if self._best_nights:
                forecast_menu = rumps.MenuItem("\U0001F4C5 Upcoming Nights")
                for title, _ in build_forecast_menu(self._best_nights):
                    forecast_menu.add(rumps.MenuItem(title, callback=None))
                self.menu.add(forecast_menu)
        else:
            for title, _ in build_loading_menu():
                self.menu.add(rumps.MenuItem(title, callback=None))

        self.menu.add(None)  # Separator

        # Actions
        refresh_title = "\U0001F504 Refreshing..." if self._is_updating else "\U0001F504 Refresh Now"
        self.menu.add(rumps.MenuItem(refresh_title, callback=self._on_refresh))

        # Preferences submenu
        prefs_menu = rumps.MenuItem("\u2699\uFE0F Preferences")
        prefs_menu.add(rumps.MenuItem("Open Config Folder...", callback=self._on_open_config))
        prefs_menu.add(rumps.MenuItem(f"Update: every {self.update_interval // 60} min", callback=None))
        self.menu.add(prefs_menu)

        self.menu.add(None)  # Separator

        # Quit
        self.menu.add(rumps.MenuItem("Quit Astrosee", callback=self._on_quit))

    def _get_location(self) -> Location | None:
        """Get the current location from config."""
        if self._location is None:
            self._location = self.config.get_default_location()
        return self._location

    def _on_timer(self, timer: rumps.Timer) -> None:
        """Handle timer tick - runs on main thread."""
        self._do_update()

    def _on_refresh(self, sender: rumps.MenuItem) -> None:
        """Handle refresh button click."""
        if not self._is_updating:
            self._do_update()

    def _on_open_config(self, _: rumps.MenuItem) -> None:
        """Open the config folder in Finder."""
        import subprocess

        subprocess.run(["open", str(self.config.config_dir)])

    def _on_quit(self, _: rumps.MenuItem) -> None:
        """Handle quit button click."""
        self._timer.stop()
        rumps.quit_application()

    def _do_update(self) -> None:
        """Perform the update synchronously (runs on main thread)."""
        if self._is_updating:
            return

        self._is_updating = True
        # Keep icon, no title change during update

        try:
            # Run async code synchronously
            asyncio.run(self._update_conditions())
        except Exception as e:
            logger.error(f"Update failed: {e}")
            self._last_error = str(e)
        finally:
            self._is_updating = False
            self._update_ui()

    async def _update_conditions(self) -> None:
        """Fetch and update current conditions."""
        location = self._get_location()
        if not location:
            self._last_error = "No location configured"
            return

        cache = CacheManager(self.config.cache_db_path)
        seeing_service = SeeingService(
            cache_manager=cache,
            cache_ttl_hours=self.config.cache_ttl_hours,
        )
        forecast_service = ForecastService(seeing_service)

        try:
            # Get current conditions
            report = await seeing_service.get_current_conditions(location)
            self._last_report = report
            self._last_error = None

            # Get best nights forecast
            try:
                self._best_nights = await forecast_service.get_best_nights(
                    location, days=7, min_score=50
                )
            except Exception as e:
                logger.warning(f"Failed to get forecast: {e}")
                self._best_nights = []

            # Get best window tonight
            try:
                window = await forecast_service.find_best_window(
                    location, hours=24, min_score=50, min_duration_hours=2
                )
                if window:
                    self._best_window = (
                        window.start,
                        window.end,
                        window.average_score,
                    )
                else:
                    self._best_window = (None, None, None)
            except Exception as e:
                logger.warning(f"Failed to get best window: {e}")
                self._best_window = (None, None, None)

        except AstroseeError as e:
            logger.error(f"Failed to update conditions: {e}")
            self._last_error = str(e)

        except Exception as e:
            logger.error(f"Unexpected error updating conditions: {e}")
            self._last_error = "Connection error"

        finally:
            await seeing_service.close()

    def _update_ui(self) -> None:
        """Update the menu bar and rebuild menu."""
        # Keep using the icon, no title text
        self.title = None
        self._build_menu()

    def run(self) -> None:
        """Run the widget application."""
        # Do initial update
        self._do_update()
        # Start timer for periodic updates
        self._timer.start()
        super().run()


def main() -> None:
    """Main entry point for the widget."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Check for location configuration
    config = ConfigManager()
    if not config.get_default_location():
        rumps.notification(
            title="Astrosee Widget",
            subtitle="No location configured",
            message="Run 'astrosee config set' to configure your location first.",
        )

    widget = AstroseeWidget(config=config)
    widget.run()


if __name__ == "__main__":
    main()
