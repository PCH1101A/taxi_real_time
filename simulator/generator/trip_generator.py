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
from generator.road_router import get_road_waypoints

log = logging.getLogger(__name__)


# ── NYC Geographic Highway / Bridge Corridors (prevents driving into water) ──

# Belt Parkway along Jamaica Bay north shoreline (from Bay Ridge / Verrazzano east to JFK)
_BELT_PKWY_EASTBOUND: List[Tuple[float, float]] = [
    (40.6066, -74.0380),  # Verrazzano Bridge / Bay Ridge
    (40.5966, -74.0028),  # Gravesend Bay / Bensonhurst
    (40.5855, -73.9899),  # Coney Island Creek
    (40.5841, -73.9640),  # Sheepshead Bay
    (40.5838, -73.9190),  # Marine Park / Plumb Beach
    (40.5976, -73.9069),  # Mill Basin Bridge
    (40.6098, -73.8976),  # Paerdegat Basin
    (40.6313, -73.8847),  # Canarsie
    (40.6464, -73.8738),  # Fresh Creek
    (40.6598, -73.8536),  # Spring Creek / Gateway Center
    (40.6664, -73.8405),  # Conduit Ave / Cross Bay Blvd junction
    (40.6631, -73.8118),  # North Conduit / Lefferts Blvd
    (40.6499, -73.8046),  # JFK Expressway approach
    (40.6428, -73.7895),  # JFK Airport Terminals
]

# Cross Bay Blvd corridor across Jamaica Bay (Queens Mainland <-> Rockaways)
_CROSS_BAY_SOUTHBOUND: List[Tuple[float, float]] = [
    (40.6664, -73.8405),  # Conduit Ave / Ozone Park
    (40.6580, -73.8420),  # Howard Beach
    (40.6120, -73.8210),  # Broad Channel (center island)
    (40.5880, -73.8180),  # Cross Bay Veterans Memorial Bridge
]

# Marine Parkway Bridge corridor (South Brooklyn <-> Rockaways)
_MARINE_PKWY_SOUTHBOUND: List[Tuple[float, float]] = [
    (40.6030, -73.9140),  # Flatbush Ave / Belt Pkwy junction
    (40.5843, -73.8950),  # Floyd Bennett Field
    (40.5735, -73.8845),  # Marine Parkway-Gil Hodges Bridge
    (40.5700, -73.8820),  # Jacob Riis Park / Rockaway Beach Blvd
]

# Gowanus Expressway corridor (Bay Ridge / Verrazzano <-> Battery Tunnel)
_GOWANUS_NORTHBOUND: List[Tuple[float, float]] = [
    (40.6139, -74.0281),  # Bay Ridge (86th St)
    (40.6326, -74.0160),  # Sunset Park South
    (40.6550, -74.0050),  # Sunset Park North / 39th St
    (40.6780, -73.9980),  # Carroll Gardens / BQE split
]


def _route_belt_parkway(s_lat: float, s_lng: float, t_lat: float, t_lng: float) -> List[Tuple[float, float]]:
    """Dynamically slices the Belt Parkway corridor from start to target without touching Jamaica Bay."""
    entry_idx = min(
        range(len(_BELT_PKWY_EASTBOUND)),
        key=lambda i: math.hypot(_BELT_PKWY_EASTBOUND[i][0] - s_lat, _BELT_PKWY_EASTBOUND[i][1] - s_lng),
    )
    exit_idx = min(
        range(len(_BELT_PKWY_EASTBOUND)),
        key=lambda i: math.hypot(_BELT_PKWY_EASTBOUND[i][0] - t_lat, _BELT_PKWY_EASTBOUND[i][1] - t_lng),
    )
    if entry_idx == exit_idx:
        return [_BELT_PKWY_EASTBOUND[entry_idx]]
    if entry_idx < exit_idx:
        return _BELT_PKWY_EASTBOUND[entry_idx : exit_idx + 1]
    else:
        return list(reversed(_BELT_PKWY_EASTBOUND[exit_idx : entry_idx + 1]))


def get_trip_waypoints(
    s_lat: float, s_lng: float, pu_b: str, t_lat: float, t_lng: float, do_b: str
) -> List[Tuple[float, float]]:
    """
    Generate realistic land/bridge waypoints for NYC taxi corridors.
    Prevents straight-line Euclidean interpolation across East River, Hudson River, Upper Bay, Jamaica Bay, etc.
    """
    pu_b = (pu_b or "").strip()
    do_b = (do_b or "").strip()
    waypoints: List[Tuple[float, float]] = [(s_lat, s_lng)]

    # Same borough routing
    if pu_b == do_b:
        if pu_b == "Queens":
            # Queens Mainland <-> Rockaways (Jamaica Bay crossing via Cross Bay Bridge)
            if s_lat < 40.605 and t_lat >= 40.605:
                waypoints.extend(reversed(_CROSS_BAY_SOUTHBOUND))
            elif s_lat >= 40.605 and t_lat < 40.605:
                # If originating near JFK, use Conduit Ave first to avoid Shellbank Basin water
                if s_lng > -73.82:
                    waypoints.append((40.6631, -73.8118))
                waypoints.extend(_CROSS_BAY_SOUTHBOUND)
            elif (s_lat > 40.77 and s_lng > -73.855 and t_lat < 40.77 and t_lng < -73.855) or \
                 (t_lat > 40.77 and t_lng > -73.855 and s_lat < 40.77 and s_lng < -73.855):
                # College Point <-> East Elmhurst/Corona (Flushing Bay bypass)
                waypoints.append((40.7600, -73.8420))
        elif pu_b == "Brooklyn":
            # Intra-Brooklyn: South Brooklyn (Coney/Bay Ridge) <-> East Brooklyn (Canarsie/Spring Creek)
            if (s_lng < -73.96 and t_lng > -73.90) or (s_lng > -73.90 and t_lng < -73.96):
                if s_lat < 40.65 or t_lat < 40.65:
                    waypoints.extend(_route_belt_parkway(s_lat, s_lng, t_lat, t_lng))
        elif pu_b == "Manhattan" and abs(s_lng - t_lng) > 0.015:
            # Intra-Manhattan: align with Manhattan grid to avoid cutting across riverbanks
            mid_lat = (s_lat + t_lat) * 0.5
            mid_lng = (s_lng + t_lng) * 0.5
            mid_lng = max(-74.015, min(-73.935, mid_lng))
            waypoints.append((mid_lat, mid_lng))

        waypoints.append((t_lat, t_lng))
        return waypoints

    avg_lat = (s_lat + t_lat) / 2.0

    # 1. Staten Island crossings (Verrazzano-Narrows Bridge is mandatory)
    if pu_b == "Staten Island" or do_b == "Staten Island":
        other_b = do_b if pu_b == "Staten Island" else pu_b
        if other_b == "EWR":
            waypoints.append((40.6350, -74.1950))  # Goethals Bridge
        else:
            if pu_b == "Staten Island":
                if s_lng < -74.08:
                    waypoints.append((40.6086, -74.1262))  # I-278 SI Expressway
                waypoints.append((40.6066, -74.0447))  # Verrazzano Bridge
                if other_b == "Queens":
                    if t_lat < 40.68 and t_lng > -73.86:  # JFK / South Queens
                        waypoints.extend(_route_belt_parkway(40.6066, -74.0380, t_lat, t_lng))
                    else:
                        waypoints.extend(_GOWANUS_NORTHBOUND)
                        waypoints.append((40.7275, -73.9345))  # Kosciuszko Bridge
                elif other_b == "Manhattan":
                    waypoints.extend(_GOWANUS_NORTHBOUND)
                    waypoints.append((40.6958, -74.0135))  # Battery Tunnel
                elif other_b == "Bronx":
                    waypoints.extend(_GOWANUS_NORTHBOUND)
                    waypoints.append((40.7850, -73.9150))  # RFK Bridge
            else:  # do_b == "Staten Island"
                if other_b == "Queens":
                    if s_lat < 40.68 and s_lng > -73.86:  # From JFK / South Queens
                        waypoints.extend(_route_belt_parkway(s_lat, s_lng, 40.6066, -74.0380))
                    else:
                        waypoints.append((40.7275, -73.9345))  # Kosciuszko Bridge
                        waypoints.extend(reversed(_GOWANUS_NORTHBOUND))
                elif other_b == "Manhattan":
                    waypoints.append((40.6958, -74.0135))  # Battery Tunnel
                    waypoints.extend(reversed(_GOWANUS_NORTHBOUND))
                elif other_b == "Bronx":
                    waypoints.append((40.7850, -73.9150))  # RFK Bridge
                    waypoints.extend(reversed(_GOWANUS_NORTHBOUND))
                waypoints.append((40.6066, -74.0447))  # Verrazzano Bridge
                if t_lng < -74.08:
                    waypoints.append((40.6086, -74.1262))  # I-278 SI Expressway

    # 2. EWR / New Jersey crossings (Holland / Lincoln Tunnel / Pulaski Skyway)
    elif pu_b == "EWR" or do_b == "EWR":
        if pu_b == "EWR":
            waypoints.append((40.7250, -74.0700))  # Pulaski / NJ Turnpike
            if avg_lat < 40.745:
                waypoints.append((40.7262, -74.0180))  # Holland Tunnel
            else:
                waypoints.append((40.7600, -74.0040))  # Lincoln Tunnel
            if do_b == "Brooklyn":
                waypoints.append((40.7070, -73.9930))  # Manhattan Bridge
            elif do_b == "Queens" and t_lat < 40.74:
                waypoints.append((40.7445, -73.9635))  # Queens-Midtown Tunnel
        else:
            if pu_b == "Brooklyn":
                waypoints.append((40.7070, -73.9930))  # Manhattan Bridge
            elif pu_b == "Queens" and s_lat < 40.74:
                waypoints.append((40.7445, -73.9635))  # Queens-Midtown Tunnel
            if avg_lat < 40.745:
                waypoints.append((40.7262, -74.0180))  # Holland Tunnel
            else:
                waypoints.append((40.7600, -74.0040))  # Lincoln Tunnel
            waypoints.append((40.7250, -74.0700))  # Pulaski / NJ Turnpike

    # 3. Brooklyn <-> Queens
    elif (pu_b == "Brooklyn" and do_b == "Queens") or (pu_b == "Queens" and do_b == "Brooklyn"):
        # Brooklyn <-> Rockaways (Marine Parkway Bridge)
        if (pu_b == "Brooklyn" and t_lat < 40.605) or (do_b == "Brooklyn" and s_lat < 40.605):
            if s_lat >= 40.605:
                waypoints.extend(_MARINE_PKWY_SOUTHBOUND)
            else:
                waypoints.extend(reversed(_MARINE_PKWY_SOUTHBOUND))
        # Brooklyn <-> South Queens / JFK / Jamaica Bay bypass
        elif (s_lat < 40.68 and t_lat < 40.68) or (s_lng < -73.89 and t_lng > -73.86) or (s_lng > -73.86 and t_lng < -73.89):
            waypoints.extend(_route_belt_parkway(s_lat, s_lng, t_lat, t_lng))
        else:
            # North Brooklyn <-> Queens (Newtown Creek crossings)
            if avg_lat > 40.730:
                waypoints.append((40.7380, -73.9535))  # Pulaski Bridge
            else:
                waypoints.append((40.7275, -73.9345))  # Kosciuszko Bridge

    # 4. Manhattan <-> Brooklyn (East River Bridges)
    elif (pu_b == "Manhattan" and do_b == "Brooklyn") or (pu_b == "Brooklyn" and do_b == "Manhattan"):
        if avg_lat <= 40.710:
            waypoints.append((40.7070, -73.9930))  # Brooklyn / Manhattan Bridge
        elif avg_lat <= 40.735:
            waypoints.append((40.7135, -73.9723))  # Williamsburg Bridge
        else:
            # North Brooklyn <-> Midtown/Upper Manhattan via Queensboro + Pulaski
            if pu_b == "Brooklyn":
                waypoints.append((40.7380, -73.9535))  # Pulaski Bridge first
                waypoints.append((40.7570, -73.9542))  # Queensboro Bridge
            else:
                waypoints.append((40.7570, -73.9542))  # Queensboro Bridge first
                waypoints.append((40.7380, -73.9535))  # Pulaski Bridge

    # 5. Manhattan <-> Queens (Queens-Midtown Tunnel, Queensboro Bridge, RFK)
    elif (pu_b == "Manhattan" and do_b == "Queens") or (pu_b == "Queens" and do_b == "Manhattan"):
        if avg_lat < 40.748:
            waypoints.append((40.7445, -73.9635))  # Queens-Midtown Tunnel
        elif avg_lat < 40.780:
            waypoints.append((40.7570, -73.9542))  # Queensboro Bridge
        else:
            waypoints.append((40.7760, -73.9240))  # RFK Bridge

    # 6. Manhattan <-> Bronx (Harlem River Bridges)
    elif (pu_b == "Manhattan" and do_b == "Bronx") or (pu_b == "Bronx" and do_b == "Manhattan"):
        if avg_lat < 40.825:
            waypoints.append((40.8105, -73.9315))  # Willis / 3rd Ave Bridge
        elif avg_lat < 40.855:
            waypoints.append((40.8285, -73.9335))  # Macombs Dam Bridge
        else:
            waypoints.append((40.8730, -73.9110))  # Broadway Bridge

    # 7. Queens <-> Bronx (Whitestone, Throgs Neck, RFK)
    elif (pu_b == "Queens" and do_b == "Bronx") or (pu_b == "Bronx" and do_b == "Queens"):
        if avg_lat > 40.77 and s_lng < -73.88:
            waypoints.append((40.7850, -73.9150))  # RFK Bridge
        else:
            waypoints.append((40.8035, -73.8300))  # Bronx-Whitestone Bridge

    else:
        # Fallback East River safeguard
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


def calculate_speed_and_steps(
    dist_miles: float,
    pu_borough: str,
    do_borough: str,
    pu_id: int,
    do_id: int,
) -> Tuple[float, int]:
    """
    Computes realistic speed (mph) and total simulation steps based on trip distance and geography.
    1. Distance scaling: The longer the trip distance, the faster the speed (highway cruising vs city congestion).
    2. Duration scaling: The longer the trip distance, the longer the trip duration (proportional simulation steps).
    """
    d = max(0.2, float(dist_miles or 0.0))

    # Base speed follows a smooth logarithmic saturation curve
    # d = 0.5 mi  -> ~11.5 mph
    # d = 2.0 mi  -> ~18.5 mph
    # d = 6.0 mi  -> ~33.0 mph
    # d = 15.0 mi -> ~47.5 mph
    # d >= 25.0 mi -> ~55.0 - 62.0 mph
    base_speed = 9.0 + 49.0 * (1.0 - math.exp(-d / 8.2))

    # Regional traffic adjustments
    is_airport = pu_id in (132, 138, 1) or do_id in (132, 138, 1)
    is_dense_manhattan = (pu_borough == "Manhattan" and do_borough == "Manhattan" and d < 4.0)

    if is_airport:
        base_speed *= 1.15
    elif is_dense_manhattan:
        base_speed *= 0.85
    elif pu_borough == "Staten Island" or do_borough == "Staten Island":
        base_speed *= 1.10

    # Slight realistic traffic variance (+-7%)
    variance = random.uniform(0.93, 1.07)
    speed = round(max(7.5, min(65.0, base_speed * variance)), 1)

    # Simulation duration (steps):
    # Proportional to real travel time (distance / speed).
    time_hours = d / speed
    steps = max(18, int(time_hours * 720))

    return speed, steps


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
    current_speed: float = 15.0
    cruising_speed: float = 25.0

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
        # Zero lateral jitter so vehicles strictly adhere to road centerlines
        new_lat, new_lng = interpolate_polyline(active.waypoints, progress, (0.0, 0.0))

        # Dynamic in-flight speed:
        # - Acceleration during initial 12% (pulling out from curb / pickup)
        # - Cruising speed during mid-trip (12% - 88%)
        # - Deceleration during final 12% (approaching dropoff zone)
        target_speed = active.cruising_speed
        if progress < 0.12:
            phase_factor = 0.65 + (progress / 0.12) * 0.35
            target_speed *= phase_factor
        elif progress > 0.88:
            phase_factor = 0.65 + ((1.0 - progress) / 0.12) * 0.35
            target_speed *= phase_factor

        jitter_speed = random.uniform(-0.8, 0.8)
        active.current_speed = round(max(6.0, min(65.0, target_speed + jitter_speed)), 1)

        now = datetime.now(timezone.utc)

        if progress >= 1.0:
            completed = active.event.model_copy(update={
                "event_type": EventType.TRIP_COMPLETED,
                "dropoff_datetime": now,
                "current_lat": active.target_lat,
                "current_lng": active.target_lng,
                "dropoff_zone_name": active.dropoff_zone_name,
                "dropoff_borough": active.dropoff_borough,
                "speed_mph": active.current_speed,
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
                "speed_mph": active.current_speed,
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

        initial_speed, _ = calculate_speed_and_steps(
            dist, pu.borough, do.borough, pu.zone_id, do.zone_id
        )

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
            speed_mph=initial_speed,
            progress_ratio=0.0,
            timestamp=time.time(),
        )

    def _register(self, event: TripEvent) -> None:
        """Store active-trip metadata for lifecycle management."""
        do = self._zones.get_or_random(event.DOLocationID)
        speed, steps = calculate_speed_and_steps(
            event.trip_distance, event.pickup_borough, do.borough, event.PULocationID, do.zone_id
        )

        waypoints = get_road_waypoints(
            s_lat=event.current_lat,
            s_lng=event.current_lng,
            pu_id=event.PULocationID,
            pu_b=event.pickup_borough,
            t_lat=do.lat,
            t_lng=do.lng,
            do_id=do.zone_id,
            do_b=do.borough,
        )

        if waypoints:
            event.current_lat = waypoints[0][0]
            event.current_lng = waypoints[0][1]

        self._active[event.trip_id] = _ActiveTrip(
            event=event,
            start_lat=waypoints[0][0] if waypoints else event.current_lat,
            start_lng=waypoints[0][1] if waypoints else event.current_lng,
            target_lat=waypoints[-1][0] if waypoints else do.lat,
            target_lng=waypoints[-1][1] if waypoints else do.lng,
            dropoff_zone_name=do.zone_name,
            dropoff_borough=do.borough,
            total_steps=steps,
            waypoints=waypoints,
            current_speed=speed,
            cruising_speed=speed,
        )
