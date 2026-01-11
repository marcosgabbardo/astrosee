"""Chart rendering with iTerm2 inline images and ASCII fallback."""

import io
import os
import sys
from base64 import b64encode
from datetime import datetime

from astrosee.display.formatters import get_score_color
from astrosee.scoring.models import SeeingForecast


class ChartRenderer:
    """Renders charts with iTerm2 inline images or ASCII fallback."""

    def __init__(self, force_ascii: bool = False):
        """Initialize chart renderer.

        Args:
            force_ascii: Force ASCII output even if iTerm2 detected
        """
        self.force_ascii = force_ascii

    def is_iterm2(self) -> bool:
        """Check if running in iTerm2 with inline image support.

        Returns:
            True if iTerm2 detected and stdout is a TTY
        """
        if self.force_ascii:
            return False

        # Must be a real terminal, not piped or in an IDE
        if not sys.stdout.isatty():
            return False

        # Check multiple environment variables that iTerm2 sets
        term_program = os.environ.get("TERM_PROGRAM", "")
        lc_terminal = os.environ.get("LC_TERMINAL", "")
        iterm_session = os.environ.get("ITERM_SESSION_ID", "")

        # Only return True if we're confident it's iTerm2
        is_iterm = (
            term_program == "iTerm.app" or
            lc_terminal == "iTerm2" or
            bool(iterm_session)
        )

        return is_iterm

    def render_score_timeline(
        self,
        forecasts: list[SeeingForecast],
        width: int = 60,
        height: int = 12,
    ) -> str:
        """Render score timeline chart.

        Args:
            forecasts: List of forecasts to plot
            width: Chart width
            height: Chart height

        Returns:
            Chart as string (ASCII or iTerm2 escape codes)
        """
        if not forecasts:
            return "No data to display"

        if self.is_iterm2():
            return self._render_matplotlib_chart(forecasts, width, height)
        else:
            return self._render_ascii_chart(forecasts, width, height)

    def _render_ascii_chart(
        self,
        forecasts: list[SeeingForecast],
        width: int,
        height: int,
    ) -> str:
        """Render ASCII chart using block characters.

        Args:
            forecasts: Forecasts to plot
            width: Chart width
            height: Chart height

        Returns:
            ASCII chart string
        """
        scores = [f.score.total_score for f in forecasts]

        # Resample if needed
        if len(scores) > width:
            step = len(scores) / width
            scores = [scores[int(i * step)] for i in range(width)]

        # Build the chart
        lines = []

        # Y-axis scale
        max_score = 100
        min_score = 0

        # Chart body
        for row in range(height):
            threshold = max_score - (row / (height - 1)) * (max_score - min_score)
            line = []

            for score in scores:
                if score >= threshold:
                    # Use different characters based on fill level
                    fill = (score - threshold) / (max_score - min_score) * (height - 1)
                    if fill > 0.75:
                        line.append("█")
                    elif fill > 0.5:
                        line.append("▆")
                    elif fill > 0.25:
                        line.append("▄")
                    else:
                        line.append("▂")
                else:
                    line.append(" ")

            # Y-axis label
            if row == 0:
                label = "100"
            elif row == height - 1:
                label = "  0"
            elif row == height // 2:
                label = " 50"
            else:
                label = "   "

            lines.append(f"{label} ┤{''.join(line)}")

        # X-axis
        lines.append("    └" + "─" * len(scores))

        # X-axis labels (times)
        if forecasts:
            first_time = forecasts[0].timestamp.strftime("%H:%M")
            mid_time = forecasts[len(forecasts) // 2].timestamp.strftime("%H:%M")
            last_time = forecasts[-1].timestamp.strftime("%H:%M")

            label_line = f"     {first_time}" + " " * (len(scores) // 2 - 8) + mid_time
            label_line += " " * (len(scores) - len(label_line) - 5 + 5) + last_time
            lines.append(label_line)

        return "\n".join(lines)

    def _render_matplotlib_chart(
        self,
        forecasts: list[SeeingForecast],
        width: int,
        height: int,
    ) -> str:
        """Render chart using matplotlib for iTerm2.

        Args:
            forecasts: Forecasts to plot
            width: Chart width (characters)
            height: Chart height (characters)

        Returns:
            iTerm2 escape sequence with inline image
        """
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
        except ImportError:
            return self._render_ascii_chart(forecasts, width, height)

        # Create figure
        fig_width = width / 10  # Convert chars to inches approximately
        fig_height = height / 4
        fig, ax = plt.subplots(figsize=(fig_width, fig_height))

        times = [f.timestamp for f in forecasts]
        scores = [f.score.total_score for f in forecasts]

        # Plot with gradient fill
        ax.plot(times, scores, linewidth=2, color="#00A0FF")
        ax.fill_between(times, scores, alpha=0.3, color="#00A0FF")

        # Styling
        ax.set_ylim(0, 100)
        ax.set_ylabel("Score", fontsize=10)
        ax.grid(True, alpha=0.3)

        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        plt.xticks(rotation=45, fontsize=8)
        plt.yticks(fontsize=8)

        # Add horizontal lines for quality thresholds
        ax.axhline(y=85, color="green", linestyle="--", alpha=0.5, linewidth=0.5)
        ax.axhline(y=55, color="yellow", linestyle="--", alpha=0.5, linewidth=0.5)
        ax.axhline(y=25, color="red", linestyle="--", alpha=0.5, linewidth=0.5)

        plt.tight_layout()

        # Save to buffer
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100, facecolor="white")
        plt.close(fig)

        buf.seek(0)
        return self._iterm2_image(buf.read())

    def _iterm2_image(self, image_data: bytes) -> str:
        """Create iTerm2 inline image escape sequence.

        Args:
            image_data: PNG image data

        Returns:
            iTerm2 escape sequence
        """
        b64_data = b64encode(image_data).decode("ascii")

        # iTerm2 proprietary escape sequence for inline images
        return f"\033]1337;File=inline=1:{b64_data}\a"

    def render_daily_sparkline(
        self,
        daily_scores: list[tuple[datetime, float]],
    ) -> str:
        """Render a sparkline for daily scores.

        Args:
            daily_scores: List of (date, score) tuples

        Returns:
            Sparkline string
        """
        if not daily_scores:
            return ""

        # Sparkline characters (8 levels)
        chars = " ▁▂▃▄▅▆▇█"

        result = []
        for _, score in daily_scores:
            # Map score (0-100) to character index (0-8)
            idx = min(8, int(score / 100 * 8))
            result.append(chars[idx])

        return "".join(result)

    def render_component_bars(
        self,
        components: dict[str, float],
        width: int = 20,
    ) -> str:
        """Render component scores as horizontal bars.

        Args:
            components: Component name to score mapping
            width: Bar width

        Returns:
            Formatted string with bars
        """
        lines = []

        component_names = {
            "temperature_differential": "Temp Stability",
            "wind_stability": "Wind",
            "humidity": "Humidity",
            "cloud_cover": "Clouds",
            "jet_stream": "Jet Stream",
        }

        for key, score in components.items():
            name = component_names.get(key, key)
            filled = int(score / 100 * width)
            bar = "█" * filled + "░" * (width - filled)
            lines.append(f"{name:15} {bar} {score:5.1f}")

        return "\n".join(lines)

    def render_altitude_profile(
        self,
        profile: list[tuple[datetime, float]],
        min_altitude: float = 30.0,
        width: int = 50,
        height: int = 8,
    ) -> str:
        """Render altitude profile as ASCII chart.

        Args:
            profile: List of (time, altitude) tuples
            min_altitude: Minimum altitude threshold to show as line
            width: Chart width in characters
            height: Chart height in lines

        Returns:
            ASCII chart string
        """
        if not profile:
            return "No data to display"

        if self.is_iterm2():
            return self._render_altitude_matplotlib(profile, min_altitude, width, height)
        else:
            return self._render_altitude_ascii(profile, min_altitude, width, height)

    def _render_altitude_ascii(
        self,
        profile: list[tuple[datetime, float]],
        min_altitude: float,
        width: int,
        height: int,
    ) -> str:
        """Render altitude profile as ASCII chart.

        Args:
            profile: List of (time, altitude) tuples
            min_altitude: Minimum altitude threshold
            width: Chart width
            height: Chart height

        Returns:
            ASCII chart string
        """
        altitudes = [alt for _, alt in profile]

        # Calculate max altitude (round up to nearest 10)
        max_alt = max(90, ((max(altitudes) + 10) // 10) * 10)
        min_alt = 0

        # Resample if needed
        if len(altitudes) > width:
            step = len(altitudes) / width
            resampled = []
            for i in range(width):
                idx = int(i * step)
                resampled.append(altitudes[idx])
            altitudes = resampled

        lines = []

        # Chart body
        for row in range(height):
            threshold = max_alt - (row / (height - 1)) * (max_alt - min_alt)
            line = []

            for alt in altitudes:
                if alt >= threshold:
                    line.append("█")
                else:
                    line.append(" ")

            # Y-axis label
            if row == 0:
                label = f"{int(max_alt):3d}°"
            elif row == height - 1:
                label = f"{int(min_alt):3d}°"
            else:
                mid_val = max_alt - (row / (height - 1)) * (max_alt - min_alt)
                if abs(mid_val - min_altitude) < (max_alt - min_alt) / height:
                    label = f"{int(min_altitude):3d}°"
                else:
                    label = "    "

            # Mark minimum altitude threshold
            if abs(threshold - min_altitude) < (max_alt - min_alt) / height:
                lines.append(f"{label}┤{''.join(line)} ← min")
            else:
                lines.append(f"{label}┤{''.join(line)}")

        # X-axis
        lines.append("    └" + "─" * len(altitudes))

        # X-axis labels
        if profile:
            first_time = profile[0][0].strftime("%H:%M")
            mid_idx = len(profile) // 2
            mid_time = profile[mid_idx][0].strftime("%H:%M")
            last_time = profile[-1][0].strftime("%H:%M")

            spacing = len(altitudes) // 2 - 5
            label_line = f"     {first_time}" + " " * max(0, spacing) + mid_time
            remaining = len(altitudes) - len(label_line) + 5
            label_line += " " * max(0, remaining - 5) + last_time
            lines.append(label_line)

        return "\n".join(lines)

    def _render_altitude_matplotlib(
        self,
        profile: list[tuple[datetime, float]],
        min_altitude: float,
        width: int,
        height: int,
    ) -> str:
        """Render altitude profile using matplotlib for iTerm2.

        Args:
            profile: List of (time, altitude) tuples
            min_altitude: Minimum altitude threshold
            width: Chart width
            height: Chart height

        Returns:
            iTerm2 escape sequence with inline image
        """
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
        except ImportError:
            return self._render_altitude_ascii(profile, min_altitude, width, height)

        times = [t for t, _ in profile]
        altitudes = [alt for _, alt in profile]

        # Create figure
        fig_width = width / 10
        fig_height = height / 3
        fig, ax = plt.subplots(figsize=(fig_width, fig_height))

        # Plot altitude curve with fill
        ax.plot(times, altitudes, linewidth=2, color="#4CAF50")
        ax.fill_between(times, altitudes, alpha=0.3, color="#4CAF50")

        # Minimum altitude threshold line
        ax.axhline(y=min_altitude, color="orange", linestyle="--",
                   alpha=0.7, linewidth=1.5, label=f"Min: {min_altitude}°")

        # Styling
        ax.set_ylim(0, max(90, max(altitudes) + 5))
        ax.set_ylabel("Altitude (°)", fontsize=10)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper right", fontsize=8)

        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        plt.xticks(rotation=45, fontsize=8)
        plt.yticks(fontsize=8)

        plt.tight_layout()

        # Save to buffer
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100, facecolor="white")
        plt.close(fig)

        buf.seek(0)
        return self._iterm2_image(buf.read())
