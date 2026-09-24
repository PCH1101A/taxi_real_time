"""Synthetic trip generator — creates randomized NYC taxi trips (no parquet needed)."""
from __future__ import annotations

import math
import random
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from models.trip_event import DatasetSource, EventType, TripEvent
from zones.zone_registry import Zone, ZoneRegistry


def _haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in miles, with realistic NYC route jitter (+20–45%)."""
    R = 3958.8
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    )
    direct = R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return max(0.5, round(direct * random.uniform(1.2, 1.45), 2))


def generate_synthetic_trip(
    zones: ZoneRegistry,
    dataset_source: Optional[DatasetSource] = None,
) -> TripEvent:
    """Generate a fully synthetic TRIP_STARTED event across Yellow, Green, or FHVHV respecting TLC regional rules."""
    # Pick dataset source if not explicitly provided
    if dataset_source is None:
        dataset_source = random.choices(
            [DatasetSource.YELLOW, DatasetSource.GREEN, DatasetSource.FHVHV],
            weights=[35, 20, 45],
            k=1,
        )[0]

    all_z = zones.zones
    manhattan_zones = [z for z in all_z if z.borough == "Manhattan"]
    airport_zones = [z for z in all_z if z.zone_id in (132, 138, 1)]  # JFK, LGA, EWR
    green_eligible_zones = [z for z in all_z if z.borough != "Manhattan" or z.lat > 40.79]
    brooklyn_zones = [z for z in all_z if z.borough == "Brooklyn"]
    queens_zones = [z for z in all_z if z.borough == "Queens"]
    bronx_zones = [z for z in all_z if z.borough == "Bronx"]
    staten_zones = [z for z in all_z if z.borough == "Staten Island"]

    if dataset_source == DatasetSource.GREEN:
        # TLC Regulation: Green cabs strictly pick up in Outer Boroughs + Northern Manhattan (north of E 96th / W 110th)
        pu = random.choice(green_eligible_zones) if green_eligible_zones else zones.random_zone()
        do = zones.random_zone()
        prefix = "gt-"
    elif dataset_source == DatasetSource.YELLOW:
        # Yellow cabs primarily pick up in Manhattan (82%) or Airport Hubs (15%)
        pu_roll = random.random()
        if pu_roll < 0.82 and manhattan_zones:
            pu = random.choice(manhattan_zones)
        elif pu_roll < 0.97 and airport_zones:
            pu = random.choice(airport_zones)
        else:
            pu = zones.random_zone()
        do = zones.random_zone()
        prefix = "yt-"
    else:  # FHVHV (Uber / Lyft)
        # FHVHV operates citywide with high outer borough ride-share demand
        borough_roll = random.choices(
            ["Brooklyn", "Manhattan", "Queens", "Bronx", "Staten Island"],
            weights=[32, 28, 24, 13, 3],
            k=1,
        )[0]
        if borough_roll == "Brooklyn" and brooklyn_zones:
            pu = random.choice(brooklyn_zones)
        elif borough_roll == "Manhattan" and manhattan_zones:
            pu = random.choice(manhattan_zones)
        elif borough_roll == "Queens" and queens_zones:
            pu = random.choice(queens_zones)
        elif borough_roll == "Bronx" and bronx_zones:
            pu = random.choice(bronx_zones)
        elif borough_roll == "Staten Island" and staten_zones:
            pu = random.choice(staten_zones)
        else:
            pu = zones.random_zone()
        do = zones.random_zone()
        prefix = "hv-"

    dist = _haversine_miles(pu.lat, pu.lng, do.lat, do.lng)
    
    if dataset_source == DatasetSource.FHVHV:
        passenger_count = 1
        payment_type = 1
    else:
        passenger_count = random.choices([1, 2, 3, 4, 5, 6], weights=[65, 18, 7, 4, 4, 2], k=1)[0]
        payment_type = random.choices([1, 2, 3, 4], weights=[72, 25, 2, 1], k=1)[0]

    if dataset_source == DatasetSource.FHVHV:
        base_rate = round(4.50 + dist * 2.80, 2)
    else:
        base_rate = round(3.00 + dist * 3.50, 2)

    fare = round(base_rate, 2)

    tip = round(fare * random.choice([0.15, 0.20, 0.25, 0.0]), 2) if payment_type == 1 else 0.0
    tolls = round(random.choice([0.0, 0.0, 6.94, 13.75]), 2) if dist > 8.0 else 0.0
    extra = 1.00 if random.random() > 0.5 else 2.50
    mta_tax = 0.50
    improvement = 1.00
    congestion = 2.50 if pu.borough == "Manhattan" else 0.00
    airport_fee = 1.75 if pu.zone_id in (132, 138) or do.zone_id in (132, 138) else 0.00
    total = round(fare + tip + tolls + extra + mta_tax + improvement + congestion + airport_fee, 2)

    now = datetime.now(timezone.utc)

    # Distance-scaled speed: longer trip distance travels much faster via highways
    d_safe = max(0.2, dist)
    base_speed = 9.0 + 49.0 * (1.0 - math.exp(-d_safe / 8.2))
    if pu.zone_id in (132, 138, 1) or do.zone_id in (132, 138, 1):
        base_speed *= 1.15
    elif pu.borough == "Manhattan" and do.borough == "Manhattan" and d_safe < 4.0:
        base_speed *= 0.85
    elif pu.borough == "Staten Island" or do.borough == "Staten Island":
        base_speed *= 1.10
    speed_mph = round(max(7.5, min(65.0, base_speed * random.uniform(0.93, 1.07))), 1)

    return TripEvent(
        trip_id=prefix + uuid.uuid4().hex[:8],
        dataset_source=dataset_source,
        event_type=EventType.TRIP_STARTED,
        pickup_datetime=now,
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
        total_amount=max(0.0, total),
        speed_mph=speed_mph,
        progress_ratio=0.0,
        timestamp=time.time(),
    )
