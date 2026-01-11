"""Export observation sessions to various formats."""

import csv
import json
from datetime import datetime
from io import StringIO
from pathlib import Path

from astrosee.services.sessions.models import ObservationSession


class SessionExporter:
    """Export observation sessions to JSON and CSV formats."""

    def __init__(self, sessions: list[ObservationSession]):
        """Initialize exporter with sessions.

        Args:
            sessions: List of sessions to export
        """
        self.sessions = sessions

    def to_json(self, indent: int = 2) -> str:
        """Export sessions to JSON string.

        Args:
            indent: JSON indentation level

        Returns:
            JSON string of all sessions
        """
        data = {
            "exported_at": datetime.now().isoformat(),
            "session_count": len(self.sessions),
            "sessions": [s.model_dump(mode="json") for s in self.sessions],
        }
        return json.dumps(data, indent=indent, default=str)

    def to_json_file(self, path: Path, indent: int = 2) -> None:
        """Export sessions to a JSON file.

        Args:
            path: Output file path
            indent: JSON indentation level
        """
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json(indent))

    def to_csv(self) -> str:
        """Export sessions summary to CSV string.

        Returns:
            CSV string with session summary
        """
        output = StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            "session_id",
            "start_time",
            "end_time",
            "duration_hours",
            "location",
            "latitude",
            "longitude",
            "initial_score",
            "rating",
            "targets_count",
            "targets",
            "equipment",
            "notes",
        ])

        # Data rows
        for session in self.sessions:
            targets = ", ".join(t.target_name for t in session.targets_observed)
            equipment = ", ".join(session.equipment_used)

            writer.writerow([
                session.id,
                session.start_time.isoformat(),
                session.end_time.isoformat() if session.end_time else "",
                f"{session.duration_hours:.2f}" if session.duration_hours else "",
                session.location.name,
                session.location.latitude,
                session.location.longitude,
                session.initial_conditions.total_score,
                session.initial_conditions.rating,
                session.target_count,
                targets,
                equipment,
                session.notes.replace("\n", " | "),
            ])

        return output.getvalue()

    def to_csv_file(self, path: Path) -> None:
        """Export sessions summary to a CSV file.

        Args:
            path: Output file path
        """
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(self.to_csv())

    def to_observations_csv(self) -> str:
        """Export individual observations to CSV string.

        Returns:
            CSV string with all observations
        """
        output = StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            "session_id",
            "session_date",
            "location",
            "target_name",
            "observed_at",
            "quality_rating",
            "altitude",
            "azimuth",
            "notes",
        ])

        # Data rows
        for session in self.sessions:
            for obs in session.targets_observed:
                writer.writerow([
                    session.id,
                    session.start_time.date().isoformat(),
                    session.location.name,
                    obs.target_name,
                    obs.observed_at.isoformat(),
                    obs.quality_rating,
                    f"{obs.altitude:.1f}" if obs.altitude else "",
                    f"{obs.azimuth:.1f}" if obs.azimuth else "",
                    obs.notes,
                ])

        return output.getvalue()

    def to_observations_csv_file(self, path: Path) -> None:
        """Export individual observations to a CSV file.

        Args:
            path: Output file path
        """
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(self.to_observations_csv())

    def to_weather_csv(self) -> str:
        """Export weather snapshots to CSV string.

        Returns:
            CSV string with weather data
        """
        output = StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            "session_id",
            "timestamp",
            "seeing_score",
            "temperature",
            "humidity",
            "cloud_cover",
            "wind_speed",
        ])

        # Data rows
        for session in self.sessions:
            for snapshot in session.weather_log:
                writer.writerow([
                    session.id,
                    snapshot.timestamp.isoformat(),
                    snapshot.seeing_score,
                    snapshot.temperature,
                    snapshot.humidity,
                    snapshot.cloud_cover,
                    snapshot.wind_speed,
                ])

        return output.getvalue()

    def to_weather_csv_file(self, path: Path) -> None:
        """Export weather snapshots to a CSV file.

        Args:
            path: Output file path
        """
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(self.to_weather_csv())
