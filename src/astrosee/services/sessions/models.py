"""Data models for observation sessions."""

from datetime import datetime

from pydantic import BaseModel, Field


class TargetObservation(BaseModel):
    """A single target observation during a session."""

    target_name: str = Field(description="Name of the observed target")
    observed_at: datetime = Field(description="Time of observation")
    quality_rating: int = Field(ge=1, le=5, description="User quality rating 1-5")
    notes: str = Field(default="", description="Observation notes")
    altitude: float | None = Field(default=None, description="Target altitude in degrees")
    azimuth: float | None = Field(default=None, description="Target azimuth in degrees")


class WeatherSnapshot(BaseModel):
    """Weather conditions at a point during the session."""

    timestamp: datetime = Field(description="Time of snapshot")
    seeing_score: float = Field(ge=0, le=100, description="Seeing score at this time")
    temperature: float = Field(description="Temperature in Celsius")
    humidity: float = Field(ge=0, le=100, description="Relative humidity %")
    cloud_cover: float = Field(ge=0, le=100, description="Cloud cover %")
    wind_speed: float = Field(description="Wind speed in m/s")


class SessionLocation(BaseModel):
    """Location information for a session."""

    name: str = Field(description="Location name")
    latitude: float = Field(ge=-90, le=90, description="Latitude")
    longitude: float = Field(ge=-180, le=180, description="Longitude")
    elevation: float | None = Field(default=None, description="Elevation in meters")


class SessionConditions(BaseModel):
    """Initial seeing conditions when session started."""

    total_score: float = Field(ge=0, le=100, description="Overall seeing score")
    rating: str = Field(description="Score rating (Excellent, Good, etc.)")
    temperature_score: float | None = Field(default=None, description="Temperature component")
    wind_score: float | None = Field(default=None, description="Wind component")
    humidity_score: float | None = Field(default=None, description="Humidity component")
    cloud_score: float | None = Field(default=None, description="Cloud component")


class ObservationSession(BaseModel):
    """Complete observation session data."""

    id: str = Field(description="Session ID (ISO timestamp format)")
    start_time: datetime = Field(description="Session start time")
    end_time: datetime | None = Field(default=None, description="Session end time")
    location: SessionLocation = Field(description="Observation location")
    initial_conditions: SessionConditions = Field(description="Conditions at session start")
    targets_observed: list[TargetObservation] = Field(
        default_factory=list, description="List of observed targets"
    )
    notes: str = Field(default="", description="General session notes")
    equipment_used: list[str] = Field(
        default_factory=list, description="Equipment IDs used"
    )
    weather_log: list[WeatherSnapshot] = Field(
        default_factory=list, description="Periodic weather snapshots"
    )

    @property
    def is_active(self) -> bool:
        """Check if session is still active (not ended)."""
        return self.end_time is None

    @property
    def duration_hours(self) -> float | None:
        """Get session duration in hours."""
        if self.end_time is None:
            return None
        delta = self.end_time - self.start_time
        return delta.total_seconds() / 3600

    @property
    def target_count(self) -> int:
        """Number of targets observed."""
        return len(self.targets_observed)

    def add_target(self, observation: TargetObservation) -> None:
        """Add a target observation to the session."""
        self.targets_observed.append(observation)

    def add_note(self, note: str) -> None:
        """Append a note to the session."""
        if self.notes:
            self.notes += f"\n{note}"
        else:
            self.notes = note

    def add_weather_snapshot(self, snapshot: WeatherSnapshot) -> None:
        """Add a weather snapshot to the log."""
        self.weather_log.append(snapshot)


class Equipment(BaseModel):
    """Equipment definition for observation sessions."""

    id: str = Field(description="Unique equipment ID (slug format)")
    name: str = Field(description="Display name")
    equipment_type: str = Field(description="Type: telescope, eyepiece, camera, mount, etc.")
    specs: dict[str, str] = Field(
        default_factory=dict, description="Equipment specifications"
    )
    notes: str = Field(default="", description="Additional notes")

    @classmethod
    def generate_id(cls, name: str) -> str:
        """Generate a slug ID from the equipment name."""
        import re
        slug = name.lower()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[\s_]+", "-", slug)
        return slug.strip("-")


class EquipmentCollection(BaseModel):
    """Collection of user equipment."""

    equipment: list[Equipment] = Field(
        default_factory=list, description="List of equipment"
    )

    def get(self, equipment_id: str) -> Equipment | None:
        """Get equipment by ID."""
        for eq in self.equipment:
            if eq.id == equipment_id:
                return eq
        return None

    def add(self, equipment: Equipment) -> None:
        """Add equipment to the collection."""
        # Remove existing with same ID
        self.equipment = [eq for eq in self.equipment if eq.id != equipment.id]
        self.equipment.append(equipment)

    def remove(self, equipment_id: str) -> bool:
        """Remove equipment by ID. Returns True if found and removed."""
        original_len = len(self.equipment)
        self.equipment = [eq for eq in self.equipment if eq.id != equipment_id]
        return len(self.equipment) < original_len

    def list_by_type(self, equipment_type: str) -> list[Equipment]:
        """List equipment by type."""
        return [eq for eq in self.equipment if eq.equipment_type == equipment_type]
