"""Unified TripEvent schema — single contract between Simulator and Kafka consumers."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class EventType(str, Enum):
    TRIP_STARTED = "TRIP_STARTED"
    LOCATION_PING = "LOCATION_PING"
    TRIP_COMPLETED = "TRIP_COMPLETED"


class DatasetSource(str, Enum):
    YELLOW = "YELLOW"
    GREEN = "GREEN"
    FHVHV = "FHVHV"


class TripEvent(BaseModel):
    # ── Identity ─────────────────────────────────────────────
    trip_id: str
    dataset_source: DatasetSource
    event_type: EventType

    # ── Time ─────────────────────────────────────────────────
    pickup_datetime: datetime
    dropoff_datetime: Optional[datetime] = None

    # ── Location ─────────────────────────────────────────────
    PULocationID: int
    DOLocationID: int
    pickup_zone_name: str
    pickup_borough: str
    dropoff_zone_name: str
    dropoff_borough: str
    current_lat: float
    current_lng: float

    # ── Trip Metrics ─────────────────────────────────────────
    passenger_count: int = Field(default=1, ge=0, le=9)
    trip_distance: float = Field(ge=0.0)   # miles, already filtered
    total_amount: float = Field(ge=0.0)    # USD, already filtered

    # ── Progress tracking (real-time lifecycle) ───────────────
    progress_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    timestamp: float = Field(default_factory=time.time)
    datetime_utc: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("trip_distance", mode="before")
    @classmethod
    def clamp_distance(cls, v: float) -> float:
        return max(0.0, min(float(v or 0.0), 200.0))

    @field_validator("total_amount", mode="before")
    @classmethod
    def clamp_amount(cls, v: float) -> float:
        return max(0.0, float(v or 0.0))

    @field_validator("passenger_count", mode="before")
    @classmethod
    def default_passenger(cls, v) -> int:
        try:
            val = int(v or 1)
            return max(0, min(val, 9))
        except (TypeError, ValueError):
            return 1

    def to_kafka_dict(self) -> dict:
        """Serialize to JSON-serializable dict for Kafka."""
        d = self.model_dump()
        # Convert datetimes to ISO strings
        for key in ("pickup_datetime", "dropoff_datetime", "datetime_utc"):
            if d[key] is not None:
                d[key] = d[key].isoformat()
        # Convert enums to string values
        d["event_type"] = self.event_type.value
        d["dataset_source"] = self.dataset_source.value
        return d
