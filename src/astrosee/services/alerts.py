"""Alert service for notifications."""

import logging
import re
import subprocess
from datetime import datetime

from astrosee.scoring.models import SeeingReport

logger = logging.getLogger(__name__)


class AlertService:
    """Service for managing and triggering alerts."""

    def __init__(self):
        """Initialize alert service."""
        self._alerts: list[dict] = []

    def add_alert(
        self,
        condition: str,
        enabled: bool = True,
        notify: bool = True,
    ) -> None:
        """Add an alert condition.

        Condition syntax:
        - "score > 80" - alert when score exceeds 80
        - "score >= 75 and cloud_cover < 20"
        - "wind_speed < 5"

        Args:
            condition: Alert condition expression
            enabled: Whether alert is active
            notify: Whether to send macOS notification
        """
        self._alerts.append({
            "condition": condition,
            "enabled": enabled,
            "notify": notify,
        })

    def remove_alert(self, index: int) -> bool:
        """Remove an alert by index.

        Args:
            index: Alert index

        Returns:
            True if removed, False if not found
        """
        if 0 <= index < len(self._alerts):
            self._alerts.pop(index)
            return True
        return False

    def evaluate(self, report: SeeingReport) -> list[dict]:
        """Evaluate all alerts against a report.

        Args:
            report: Seeing report to evaluate

        Returns:
            List of triggered alerts
        """
        triggered = []

        for alert in self._alerts:
            if not alert.get("enabled", True):
                continue

            condition = alert.get("condition", "")
            if self._evaluate_condition(condition, report):
                triggered.append(alert)

                if alert.get("notify", True):
                    self._send_notification(report, condition)

        return triggered

    def _evaluate_condition(
        self,
        condition: str,
        report: SeeingReport,
    ) -> bool:
        """Evaluate a condition expression.

        Args:
            condition: Condition string
            report: Report to evaluate against

        Returns:
            True if condition is met
        """
        # Build evaluation context
        context = {
            "score": report.score.total_score,
            "cloud_cover": report.weather.cloud_cover,
            "wind_speed": report.weather.wind_speed_10m,
            "humidity": report.weather.humidity,
            "temperature": report.weather.temperature,
            "moon_illumination": report.astronomy.moon_illumination,
            "moon_altitude": report.astronomy.moon_altitude,
        }

        try:
            # Simple and safe evaluation
            # Only allow specific operators and variable names
            safe_condition = self._sanitize_condition(condition, context)
            return eval(safe_condition, {"__builtins__": {}}, context)
        except Exception as e:
            logger.warning(f"Failed to evaluate condition '{condition}': {e}")
            return False

    def _sanitize_condition(
        self,
        condition: str,
        context: dict,
    ) -> str:
        """Sanitize condition for safe evaluation.

        Args:
            condition: Raw condition string
            context: Available variables

        Returns:
            Sanitized condition string
        """
        # Only allow these patterns
        allowed_vars = "|".join(context.keys())
        allowed_ops = r"[<>=!]+|and|or|not"
        allowed_nums = r"\d+\.?\d*"

        # Check that condition only contains allowed elements
        pattern = rf"^[\s()*]*({allowed_vars}|{allowed_ops}|{allowed_nums}|[\s()])+[\s)]*$"
        if not re.match(pattern, condition, re.IGNORECASE):
            raise ValueError(f"Invalid condition syntax: {condition}")

        return condition

    def _send_notification(
        self,
        report: SeeingReport,
        condition: str,
    ) -> None:
        """Send macOS notification.

        Args:
            report: Report that triggered alert
            condition: Condition that was met
        """
        title = "Astrosee Alert"
        message = (
            f"Seeing score: {report.score.total_score:.0f} "
            f"({report.score.rating}) at {report.location.name}"
        )
        subtitle = f"Condition met: {condition}"

        try:
            script = f'''
            display notification "{message}" with title "{title}" subtitle "{subtitle}"
            '''
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                timeout=5,
            )
            logger.info(f"Sent notification: {message}")
        except Exception as e:
            logger.warning(f"Failed to send notification: {e}")

    def get_alerts(self) -> list[dict]:
        """Get all configured alerts.

        Returns:
            List of alert configurations
        """
        return self._alerts.copy()

    def format_condition_help(self) -> str:
        """Get help text for condition syntax.

        Returns:
            Help string
        """
        return """
Alert Condition Syntax:

Available variables:
  score           - Overall seeing score (0-100)
  cloud_cover     - Cloud cover percentage (0-100)
  wind_speed      - Wind speed in m/s
  humidity        - Relative humidity (0-100)
  temperature     - Temperature in Celsius
  moon_illumination - Moon illumination percentage (0-100)
  moon_altitude   - Moon altitude in degrees

Operators:
  >  <  >=  <=  ==  !=
  and  or  not

Examples:
  "score > 80"
  "score >= 70 and cloud_cover < 30"
  "wind_speed < 5 and humidity < 70"
  "score > 75 and moon_illumination < 50"
"""
