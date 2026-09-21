"""TripGenerator — manages trip lifecycle for all 3 dataset sources."""
from __future__ import annotations

import logging
import math
import random
import time
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from loaders.fhvhv_loader import FhvhvLoader
from models.trip_event import DatasetSource, EventType, TripEvent
from zones.zone_registry import Zone, ZoneRegistry
from generator.synthetic import generate_synthetic_trip

log = logging.getLogger(__name__)


def get_trip_waypoints(
    s_lat: float, s_lng: float, pu_b: str, t_lat: float, t_lng: float, do_b: str
) -> List[Tuple[float, float]]:
    """
    Generate realistic land/bridge waypoints for NYC taxi corridors.
    Prevents straight-line Euclidean interpolation across East River, Hudson River, Upper Bay, etc.
    """
    pu_b = (pu_b or "").strip()
    do_b = (do_b or "").strip()
    
    # Same borough routing
    if pu_b == do_b:
        # Queens <-> Rockaways (Jamaica Bay crossing via Cross Bay Bridge)
        if pu_b == "Queens" and (s_lat < 40.60 or t_lat < 40.60) and abs(s_lat - t_lat) > 0.05:
            return [(s_lat, s_lng), (40.5980, -73.8180), (t_lat, t_lng)]
        # Intra-Manhattan: align with Manhattan grid avenue / street corners to avoid cutting across riverbanks
        if pu_b == "Manhattan" and abs(s_lng - t_lng) > 0.015:
            mid_lat = (s_lat + t_lat) * 0.5
            mid_lng = (s_lng + t_lng) * 0.5
            mid_lng = max(-74.015, min(-73.935, mid_lng))
            return [(s_lat, s_lng), (mid_lat, mid_lng), (t_lat, t_lng)]
        return [(s_lat, s_lng), (t_lat, t_lng)]

    waypoints: List[Tuple[float, float]] = [(s_lat, s_lng)]
    avg_lat = (s_lat + t_lat) / 2.0

    is_m_b = (pu_b == "Manhattan" and do_b == "Brooklyn") or (pu_b == "Brooklyn" and do_b == "Manhattan")
    is_m_q = (pu_b == "Manhattan" and do_b == "Queens") or (pu_b == "Queens" and do_b == "Manhattan")
    is_m_bx = (pu_b == "Manhattan" and do_b == "Bronx") or (pu_b == "Bronx" and do_b == "Manhattan")
    is_b_q = (pu_b == "Brooklyn" and do_b == "Queens") or (pu_b == "Queens" and do_b == "Brooklyn")
    is_b_si = (pu_b == "Brooklyn" and do_b == "Staten Island") or (pu_b == "Staten Island" and do_b == "Brooklyn")
    is_m_si = (pu_b == "Manhattan" and do_b == "Staten Island") or (pu_b == "Staten Island" and do_b == "Manhattan")
    is_q_bx = (pu_b == "Queens" and do_b == "Bronx") or (pu_b == "Bronx" and do_b == "Queens")
    is_ewr = pu_b == "EWR" or do_b == "EWR"

    if is_m_b:
        # 1. Manhattan <-> Brooklyn (East River Bridges)
        if avg_lat <= 40.710:
            # Brooklyn / Manhattan Bridge
            waypoints.append((40.7070, -73.9930))
        elif avg_lat <= 40.735:
            # Williamsburg Bridge
            waypoints.append((40.7135, -73.9723))
        else:
            # North Brooklyn <-> Midtown/Upper Manhattan via Queensboro + Pulaski Bridge
            waypoints.append((40.7570, -73.9542))
            waypoints.append((40.7380, -73.9535))

    elif is_m_q:
        # 2. Manhattan <-> Queens (Queens-Midtown Tunnel, Queensboro Bridge, Triborough RFK)
        if avg_lat < 40.748:
            # Queens-Midtown Tunnel
            waypoints.append((40.7445, -73.9635))
        elif avg_lat < 40.780:
            # Queensboro Bridge (59th St)
            waypoints.append((40.7570, -73.9542))
        else:
            # RFK / Triborough Bridge
            waypoints.append((40.7760, -73.9240))

    elif is_m_bx:
        # 3. Manhattan <-> Bronx (Harlem River Bridges)
        if avg_lat < 40.825:
            waypoints.append((40.8105, -73.9315))  # Willis / 3rd Ave Bridge
        elif avg_lat < 40.855:
            waypoints.append((40.8285, -73.9335))  # Macombs Dam / 145th St Bridge
        else:
            waypoints.append((40.8730, -73.9110))  # Broadway Bridge / University Heights

    elif is_b_q:
        # 4. Brooklyn <-> Queens (Newtown Creek crossings)
        if avg_lat > 40.725 and (s_lng < -73.94 or t_lng < -73.94):
            waypoints.append((40.7380, -73.9535))  # Pulaski Bridge

    elif is_b_si:
        # 5. Brooklyn <-> Staten Island (Verrazzano-Narrows Bridge)
        waypoints.append((40.6066, -74.0447))

    elif is_m_si:
        # 6. Manhattan <-> Staten Island (Battery Tunnel + Verrazzano Bridge)
        waypoints.append((40.6958, -74.0135))
        waypoints.append((40.6066, -74.0447))

    elif is_q_bx:
        # 7. Queens <-> Bronx (Whitestone, Throgs Neck, RFK)
        if avg_lat > 40.77 and s_lng < -73.88:
            waypoints.append((40.7850, -73.9150))  # RFK Bridge
        else:
            waypoints.append((40.8035, -73.8300))  # Bronx-Whitestone Bridge

    elif is_ewr:
        # 8. NYC <-> EWR / New Jersey (Holland Tunnel / Lincoln Tunnel)
        if avg_lat < 40.745:
            waypoints.append((40.7262, -74.0180))  # Holland Tunnel
        else:
            waypoints.append((40.7600, -74.0040))  # Lincoln Tunnel

    else:
        # Generic East River water crossing safeguard
        if (s_lng < -73.96 and t_lng > -73.95) or (s_lng > -73.95 and t_lng < -73.96):
            if avg_lat < 40.725:
                waypoints.append((40.7135, -73.9723))
            elif avg_lat < 40.765:
                waypoints.append((40.7570, -73.9542))
            else:
                waypoints.append((40.7760, -73.9240))

    waypoints.append((t_lat, t_lng))
    return waypoints


def interpolate_polyline(
    waypoints: List[Tuple[float, float]],
    progress: float,
    jitter: Tuple[float, float] = (0.0, 0.0),
) -> Tuple[float, float]:
    """
    Interpolate smoothly along a multi-waypoint path based on progress ratio (0.0 -> 1.0).
    Distance-weighted across segments to maintain continuous speed.
    """
    if len(waypoints) <= 1:
        return waypoints[0] if waypoints else (40.75, -73.98)

    progress = max(0.0, min(1.0, progress))
    if progress <= 0.0:
        return (round(waypoints[0][0] + jitter[0], 5), round(waypoints[0][1] + jitter[1], 5))
    if progress >= 1.0:
        return (round(waypoints[-1][0], 5), round(waypoints[-1][1], 5))

    seg_lengths = []
    total_len = 0.0
    for i in range(len(waypoints) - 1):
        p1 = waypoints[i]
        p2 = waypoints[i + 1]
        dist = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        seg_lengths.append(dist)
        total_len += dist

    if total_len == 0.0:
        return (round(waypoints[0][0] + jitter[0], 5), round(waypoints[0][1] + jitter[1], 5))

    target_dist = progress * total_len
    cum_dist = 0.0

    for i, seg_len in enumerate(seg_lengths):
        if cum_dist + seg_len >= target_dist or i == len(seg_lengths) - 1:
            seg_prog = (target_dist - cum_dist) / max(1e-7, seg_len)
            seg_prog = max(0.0, min(1.0, seg_prog))
            p1 = waypoints[i]
            p2 = waypoints[i + 1]
            lat = p1[0] + (p2[0] - p1[0]) * seg_prog + jitter[0]
            lng = p1[1] + (p2[1] - p1[1]) * seg_prog + jitter[1]
            return (round(lat, 5), round(lng, 5))
        cum_dist += seg_len

    return (round(waypoints[-1][0], 5), round(waypoints[-1][1], 5))


@dataclass
class _ActiveTrip:
    """Internal state for a trip in-progress (not sent to Kafka directly)."""
    event: TripEvent
    start_lat: float
    start_lng: float
    target_lat: float
    target_lng: float
    dropoff_zone_name: str
    dropoff_borough: str
    total_steps: int
    waypoints: List[Tuple[float, float]] = field(default_factory=list)
    current_step: int = 0

    @property
    def progress(self) -> float:
        return min(1.0, round(self.current_step / max(1, self.total_steps), 4))


class TripGenerator:
    """
    Manages the full lifecycle of simulated taxi trips.

    Responsibilities:
    - Create new TRIP_STARTED events from parquet rows or synthetic generation
    - Advance in-progress trips (LOCATION_PING)
    - Complete trips (TRIP_COMPLETED)
    """

    def __init__(self, zones: ZoneRegistry) -> None:
        self._zones = zones
        self._active: Dict[str, _ActiveTrip] = {}

    # ── Public API ─────────────────────────────────────────────────────────────

    def create_from_parquet(self, source: DatasetSource, row: Dict) -> TripEvent:
        """Create a TRIP_STARTED event from a raw parquet row."""
        if source == DatasetSource.YELLOW:
            return self._create_yellow(row)
        elif source == DatasetSource.GREEN:
            return self._create_green(row)
        else:
            return self._create_fhvhv(row)

    def create_synthetic(
        self, dataset_source: Optional[DatasetSource] = None
    ) -> TripEvent:
        """Create a fully synthetic TRIP_STARTED event."""
        event = generate_synthetic_trip(
            self._zones, dataset_source=dataset_source
        )
        self._register(event)
        return event

    def step(self, trip_id: str) -> Optional[TripEvent]:
        """
        Advance trip one step.
        Returns LOCATION_PING event, or TRIP_COMPLETED and removes from active.
        Returns None if trip_id unknown.
        """
        active = self._active.get(trip_id)
        if active is None:
            return None

        active.current_step += 1
        progress = active.progress
        jitter = (random.uniform(-0.0003, 0.0003), random.uniform(-0.0003, 0.0003))

        new_lat, new_lng = interpolate_polyline(active.waypoints, progress, jitter)
        old_speed = active.event.trip_distance / max(0.01, active.total_steps / 1800)
        new_speed = round(max(5.0, random.gauss(old_speed, 3.0)), 1)

        now = datetime.now(timezone.utc)

        if progress >= 1.0:
            completed = active.event.model_copy(update={
                "event_type": EventType.TRIP_COMPLETED,
                "dropoff_datetime": now,
                "current_lat": active.target_lat,
                "current_lng": active.target_lng,
                "dropoff_zone_name": active.dropoff_zone_name,
                "dropoff_borough": active.dropoff_borough,
                "progress_ratio": 1.0,
                "timestamp": time.time(),
                "datetime_utc": now,
            })
            del self._active[trip_id]
            return completed
        else:
            current_zone = (
                active.event.DOLocationID if progress > 0.6 else active.event.PULocationID
            )
            current_borough = (
                active.dropoff_borough if progress > 0.6 else active.event.pickup_borough
            )
            ping = active.event.model_copy(update={
                "event_type": EventType.LOCATION_PING,
                "current_lat": new_lat,
                "current_lng": new_lng,
                "progress_ratio": progress,
                "timestamp": time.time(),
                "datetime_utc": now,
            })
            return ping

    def random_active_trip_id(self) -> Optional[str]:
        if not self._active:
            return None
        return random.choice(list(self._active.keys()))

    @property
    def active_count(self) -> int:
        return len(self._active)

    # ── Internal builders ──────────────────────────────────────────────────────

    def _create_yellow(self, row: Dict) -> TripEvent:
        pu_id = int(row.get("PULocationID", 230))
        do_id = int(row.get("DOLocationID", 161))
        pu = self._zones.get_or_random(pu_id)
        do = self._zones.get_or_random(do_id)

        dist = float(row.get("trip_distance") or 0.0)
        total = float(row.get("total_amount") or 0.0)

        event = self._build_event(
            source=DatasetSource.YELLOW,
            trip_id="yl-" + uuid.uuid4().hex[:8],
            pu=pu, do=do, dist=dist, total=total,
            passenger_count=int(row.get("passenger_count") or 1),
            pickup_dt=row.get("tpep_pickup_datetime"),
        )
        self._register(event)
        return event

    def _create_green(self, row: Dict) -> TripEvent:
        pu_id = int(row.get("PULocationID", 161))
        do_id = int(row.get("DOLocationID", 230))
        pu = self._zones.get_or_random(pu_id)
        do = self._zones.get_or_random(do_id)

        dist = float(row.get("trip_distance") or 0.0)
        total = float(row.get("total_amount") or 0.0)

        event = self._build_event(
            source=DatasetSource.GREEN,
            trip_id="gn-" + uuid.uuid4().hex[:8],
            pu=pu, do=do, dist=dist, total=total,
            passenger_count=int(row.get("passenger_count") or 1),
            pickup_dt=row.get("lpep_pickup_datetime"),
        )
        self._register(event)
        return event

    def _create_fhvhv(self, row: Dict) -> TripEvent:
        pu_id = int(row.get("PULocationID", 161))
        do_id = int(row.get("DOLocationID", 230))
        pu = self._zones.get_or_random(pu_id)
        do = self._zones.get_or_random(do_id)

        dist = float(row.get("trip_miles") or 0.0)
        total = float(row.get("base_passenger_fare") or 0.0)
        provider = FhvhvLoader.provider_name(row)

        event = self._build_event(
            source=DatasetSource.FHVHV,
            trip_id="hv-" + uuid.uuid4().hex[:8],
            pu=pu, do=do, dist=dist, total=total,
            passenger_count=1,  # FHVHV does not report passenger_count
            pickup_dt=row.get("pickup_datetime"),
        )
        self._register(event)
        return event

    def _build_event(
        self,
        source: DatasetSource,
        trip_id: str,
        pu: Zone,
        do: Zone,
        dist: float,
        total: float,
        passenger_count: int,
        pickup_dt=None,
    ) -> TripEvent:
        now = datetime.now(timezone.utc)
        if isinstance(pickup_dt, datetime):
            pickup_datetime = pickup_dt if pickup_dt.tzinfo else pickup_dt.replace(tzinfo=timezone.utc)
        else:
            pickup_datetime = now

        avg_speed = random.uniform(10.0, 24.0)
        steps = max(3, int((max(0.5, dist) / avg_speed) * 3600 / 2))

        return TripEvent(
            trip_id=trip_id,
            dataset_source=source,
            event_type=EventType.TRIP_STARTED,
            pickup_datetime=pickup_datetime,
            dropoff_datetime=None,
            PULocationID=pu.zone_id,
            DOLocationID=do.zone_id,
            pickup_zone_name=pu.zone_name,
            pickup_borough=pu.borough,
            dropoff_zone_name=do.zone_name,
            dropoff_borough=do.borough,
            current_lat=pu.lat,
            current_lng=pu.lng,
            passenger_count=passenger_count,
            trip_distance=dist,
            total_amount=total,
            progress_ratio=0.0,
            timestamp=time.time(),
        )

    def _register(self, event: TripEvent) -> None:
        """Store active-trip metadata for lifecycle management."""
        do = self._zones.get_or_random(event.DOLocationID)
        avg_speed = random.uniform(10.0, 24.0)
        steps = max(3, int((max(0.5, event.trip_distance) / avg_speed) * 3600 / 2))

        waypoints = get_trip_waypoints(
            s_lat=event.current_lat,
            s_lng=event.current_lng,
            pu_b=event.pickup_borough,
            t_lat=do.lat,
            t_lng=do.lng,
            do_b=do.borough,
        )

        self._active[event.trip_id] = _ActiveTrip(
            event=event,
            start_lat=event.current_lat,
            start_lng=event.current_lng,
            target_lat=do.lat,
            target_lng=do.lng,
            dropoff_zone_name=do.zone_name,
            dropoff_borough=do.borough,
            total_steps=steps,
            waypoints=waypoints,
        )
