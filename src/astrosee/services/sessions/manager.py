"""Session and equipment management."""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

import tomli_w

from astrosee.astronomy.models import Location
from astrosee.core.exceptions import AstroseeError
from astrosee.scoring.models import SeeingReport
from astrosee.services.sessions.models import (
    Equipment,
    EquipmentCollection,
    ObservationSession,
    SessionConditions,
    SessionLocation,
    TargetObservation,
    WeatherSnapshot,
)


class SessionError(AstroseeError):
    """Session-related errors."""

    pass


class SessionManager:
    """Manages observation sessions stored as JSON files."""

    DEFAULT_DIR = Path.home() / ".astrosee"
    SESSIONS_DIRNAME = "sessions"
    EQUIPMENT_FILENAME = "equipment.toml"

    def __init__(self, config_dir: Path | None = None):
        """Initialize session manager.

        Args:
            config_dir: Custom config directory (default: ~/.astrosee/)
        """
        self.config_dir = config_dir or self.DEFAULT_DIR
        self.sessions_dir = self.config_dir / self.SESSIONS_DIRNAME
        self.equipment_file = self.config_dir / self.EQUIPMENT_FILENAME
        self._ensure_dirs_exist()

    def _ensure_dirs_exist(self) -> None:
        """Create necessary directories."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(exist_ok=True)

    @staticmethod
    def _generate_session_id() -> str:
        """Generate a session ID from current timestamp."""
        return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")

    def _session_path(self, session_id: str) -> Path:
        """Get the file path for a session."""
        return self.sessions_dir / f"{session_id}.json"

    def _save_session(self, session: ObservationSession) -> None:
        """Save a session to disk."""
        path = self._session_path(session.id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(session.model_dump(mode="json"), f, indent=2, default=str)

    def _load_session(self, session_id: str) -> ObservationSession | None:
        """Load a session from disk."""
        path = self._session_path(session_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return ObservationSession.model_validate(data)
        except Exception as e:
            raise SessionError(f"Failed to load session {session_id}: {e}") from e

    # Session operations

    def start_session(
        self,
        location: Location,
        conditions: SeeingReport,
    ) -> ObservationSession:
        """Start a new observation session.

        Args:
            location: Observation location
            conditions: Current seeing conditions

        Returns:
            The newly created session
        """
        # Check for existing active session
        active = self.get_active_session()
        if active:
            raise SessionError(
                f"Session {active.id} is already active. End it first with 'session end'."
            )

        session_id = self._generate_session_id()
        now = datetime.now()

        # Convert location
        session_location = SessionLocation(
            name=location.name,
            latitude=location.latitude,
            longitude=location.longitude,
            elevation=location.elevation,
        )

        # Convert conditions
        session_conditions = SessionConditions(
            total_score=conditions.score.total_score,
            rating=conditions.score.rating,
            temperature_score=conditions.score.component_scores.get("temperature_differential"),
            wind_score=conditions.score.component_scores.get("wind_stability"),
            humidity_score=conditions.score.component_scores.get("humidity"),
            cloud_score=conditions.score.component_scores.get("cloud_cover"),
        )

        session = ObservationSession(
            id=session_id,
            start_time=now,
            location=session_location,
            initial_conditions=session_conditions,
        )

        self._save_session(session)
        return session

    def get_active_session(self) -> ObservationSession | None:
        """Get the currently active session (if any)."""
        for session_id in self.list_session_ids():
            session = self._load_session(session_id)
            if session and session.is_active:
                return session
        return None

    def end_session(self, session_id: str | None = None) -> ObservationSession:
        """End a session.

        Args:
            session_id: Session to end (defaults to active session)

        Returns:
            The ended session
        """
        if session_id is None:
            session = self.get_active_session()
            if not session:
                raise SessionError("No active session to end")
        else:
            session = self._load_session(session_id)
            if not session:
                raise SessionError(f"Session {session_id} not found")

        if not session.is_active:
            raise SessionError(f"Session {session.id} is already ended")

        session.end_time = datetime.now()
        self._save_session(session)
        return session

    def log_observation(
        self,
        target_name: str,
        quality_rating: int,
        notes: str = "",
        altitude: float | None = None,
        azimuth: float | None = None,
        session_id: str | None = None,
    ) -> TargetObservation:
        """Log a target observation to the current session.

        Args:
            target_name: Name of the observed target
            quality_rating: Quality rating 1-5
            notes: Observation notes
            altitude: Target altitude in degrees
            azimuth: Target azimuth in degrees
            session_id: Session to add to (defaults to active session)

        Returns:
            The created observation
        """
        if session_id is None:
            session = self.get_active_session()
            if not session:
                raise SessionError("No active session. Start one with 'session start'.")
        else:
            session = self._load_session(session_id)
            if not session:
                raise SessionError(f"Session {session_id} not found")

        observation = TargetObservation(
            target_name=target_name,
            observed_at=datetime.now(),
            quality_rating=quality_rating,
            notes=notes,
            altitude=altitude,
            azimuth=azimuth,
        )

        session.add_target(observation)
        self._save_session(session)
        return observation

    def add_note(self, note: str, session_id: str | None = None) -> ObservationSession:
        """Add a note to the session.

        Args:
            note: Note text to add
            session_id: Session to add to (defaults to active session)

        Returns:
            The updated session
        """
        if session_id is None:
            session = self.get_active_session()
            if not session:
                raise SessionError("No active session. Start one with 'session start'.")
        else:
            session = self._load_session(session_id)
            if not session:
                raise SessionError(f"Session {session_id} not found")

        session.add_note(note)
        self._save_session(session)
        return session

    def add_weather_snapshot(
        self,
        seeing_score: float,
        temperature: float,
        humidity: float,
        cloud_cover: float,
        wind_speed: float,
        session_id: str | None = None,
    ) -> ObservationSession:
        """Add a weather snapshot to the session.

        Args:
            seeing_score: Current seeing score
            temperature: Temperature in Celsius
            humidity: Relative humidity %
            cloud_cover: Cloud cover %
            wind_speed: Wind speed in m/s
            session_id: Session to add to (defaults to active session)

        Returns:
            The updated session
        """
        if session_id is None:
            session = self.get_active_session()
            if not session:
                raise SessionError("No active session.")
        else:
            session = self._load_session(session_id)
            if not session:
                raise SessionError(f"Session {session_id} not found")

        snapshot = WeatherSnapshot(
            timestamp=datetime.now(),
            seeing_score=seeing_score,
            temperature=temperature,
            humidity=humidity,
            cloud_cover=cloud_cover,
            wind_speed=wind_speed,
        )

        session.add_weather_snapshot(snapshot)
        self._save_session(session)
        return session

    def set_equipment(
        self, equipment_ids: list[str], session_id: str | None = None
    ) -> ObservationSession:
        """Set equipment used in the session.

        Args:
            equipment_ids: List of equipment IDs
            session_id: Session to update (defaults to active session)

        Returns:
            The updated session
        """
        if session_id is None:
            session = self.get_active_session()
            if not session:
                raise SessionError("No active session.")
        else:
            session = self._load_session(session_id)
            if not session:
                raise SessionError(f"Session {session_id} not found")

        session.equipment_used = equipment_ids
        self._save_session(session)
        return session

    def list_session_ids(self) -> list[str]:
        """List all session IDs, sorted by date (newest first)."""
        sessions = []
        for path in self.sessions_dir.glob("*.json"):
            sessions.append(path.stem)
        return sorted(sessions, reverse=True)

    def get_session(self, session_id: str) -> ObservationSession | None:
        """Get a session by ID."""
        return self._load_session(session_id)

    def list_sessions(self, limit: int | None = None) -> list[ObservationSession]:
        """List all sessions, sorted by date (newest first).

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of sessions
        """
        session_ids = self.list_session_ids()
        if limit:
            session_ids = session_ids[:limit]

        sessions = []
        for session_id in session_ids:
            session = self._load_session(session_id)
            if session:
                sessions.append(session)
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: Session ID to delete

        Returns:
            True if deleted, False if not found
        """
        path = self._session_path(session_id)
        if path.exists():
            path.unlink()
            return True
        return False

    # Equipment operations

    def _load_equipment(self) -> EquipmentCollection:
        """Load equipment from TOML file."""
        if not self.equipment_file.exists():
            return EquipmentCollection()

        try:
            with open(self.equipment_file, "rb") as f:
                data = tomllib.load(f)
            equipment_list = []
            for eq_data in data.get("equipment", []):
                equipment_list.append(Equipment.model_validate(eq_data))
            return EquipmentCollection(equipment=equipment_list)
        except Exception as e:
            raise SessionError(f"Failed to load equipment: {e}") from e

    def _save_equipment(self, collection: EquipmentCollection) -> None:
        """Save equipment to TOML file."""
        data: dict[str, Any] = {
            "equipment": [eq.model_dump() for eq in collection.equipment]
        }
        with open(self.equipment_file, "wb") as f:
            tomli_w.dump(data, f)

    def add_equipment(
        self,
        name: str,
        equipment_type: str,
        specs: dict[str, str] | None = None,
        notes: str = "",
    ) -> Equipment:
        """Add equipment to the collection.

        Args:
            name: Equipment name
            equipment_type: Type (telescope, eyepiece, camera, mount, etc.)
            specs: Equipment specifications
            notes: Additional notes

        Returns:
            The created equipment
        """
        collection = self._load_equipment()

        equipment = Equipment(
            id=Equipment.generate_id(name),
            name=name,
            equipment_type=equipment_type,
            specs=specs or {},
            notes=notes,
        )

        collection.add(equipment)
        self._save_equipment(collection)
        return equipment

    def get_equipment(self, equipment_id: str) -> Equipment | None:
        """Get equipment by ID."""
        collection = self._load_equipment()
        return collection.get(equipment_id)

    def list_equipment(self, equipment_type: str | None = None) -> list[Equipment]:
        """List all equipment, optionally filtered by type.

        Args:
            equipment_type: Filter by type (optional)

        Returns:
            List of equipment
        """
        collection = self._load_equipment()
        if equipment_type:
            return collection.list_by_type(equipment_type)
        return collection.equipment

    def remove_equipment(self, equipment_id: str) -> bool:
        """Remove equipment by ID.

        Args:
            equipment_id: Equipment ID to remove

        Returns:
            True if removed, False if not found
        """
        collection = self._load_equipment()
        if collection.remove(equipment_id):
            self._save_equipment(collection)
            return True
        return False
