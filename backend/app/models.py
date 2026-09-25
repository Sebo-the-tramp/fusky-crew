"""API and provider data models."""

from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class TrackPointReading:
    """One sanitized point in a recorded location trail."""

    latitude: float
    longitude: float
    reported_at: datetime


@dataclass(frozen=True)
class LocationReading:
    """Provider-neutral location reading."""

    device_name: str
    latitude: float
    longitude: float
    reported_at: datetime
    accuracy_m: int | None
    source: str
    track: tuple[TrackPointReading, ...] = ()


class TrackPointResponse(BaseModel):
    """One browser-safe point in a recorded location trail."""

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    reported_at: datetime


class LocationResponse(BaseModel):
    """Minimal location payload safe to return to an authorized browser."""

    device_name: str
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    reported_at: datetime
    fetched_at: datetime
    accuracy_m: int | None = Field(default=None, ge=0)
    source: str
    stale: bool
    track: list[TrackPointResponse] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """Non-sensitive service health payload."""

    status: str
    provider: str
