"""ZoneRegistry — loads taxi_zones.json, provides fast lookup by LocationID."""
from __future__ import annotations

import json
import logging
import os
import random
from dataclasses import dataclass
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

_DEFAULT_ZONES = [
    {"zone_id": 132, "zone_name": "JFK Airport",                  "borough": "Queens",     "lat": 40.64269, "lng": -73.78965, "base_demand": 2.5},
    {"zone_id": 138, "zone_name": "LaGuardia Airport",            "borough": "Queens",     "lat": 40.77486, "lng": -73.87344, "base_demand": 2.5},
    {"zone_id": 161, "zone_name": "Midtown Center",               "borough": "Manhattan",  "lat": 40.75803, "lng": -73.97769, "base_demand": 2.0},
    {"zone_id": 230, "zone_name": "Times Sq/Theatre District",    "borough": "Manhattan",  "lat": 40.75982, "lng": -73.9842,  "base_demand": 2.0},
    {"zone_id": 234, "zone_name": "Union Sq",                     "borough": "Manhattan",  "lat": 40.73600, "lng": -73.9905,  "base_demand": 2.0},
    {"zone_id":  87, "zone_name": "Financial District North",     "borough": "Manhattan",  "lat": 40.70900, "lng": -74.0090,  "base_demand": 2.0},
    {"zone_id":  65, "zone_name": "Downtown Brooklyn/MetroTech",  "borough": "Brooklyn",   "lat": 40.69300, "lng": -73.9850,  "base_demand": 1.5},
]


@dataclass
class Zone:
    zone_id: int
    zone_name: str
    borough: str
    lat: float
    lng: float
    base_demand: float


class ZoneRegistry:
    """Immutable registry of 263 NYC taxi zones, loaded once at startup."""

    def __init__(self, json_path: Optional[str] = None) -> None:
        raw = self._load(json_path)
        self._zones: List[Zone] = [
            Zone(
                zone_id=int(z["zone_id"]),
                zone_name=z.get("zone_name", f"Zone {z['zone_id']}"),
                borough=z.get("borough", "Manhattan"),
                lat=float(z.get("lat", 40.75)),
                lng=float(z.get("lng", -73.98)),
                base_demand=float(z.get("base_demand", 1.0)),
            )
            for z in raw
        ]
        self._by_id: Dict[int, Zone] = {z.zone_id: z for z in self._zones}
        self._weights: List[float] = [z.base_demand for z in self._zones]
        log.info("ZoneRegistry loaded %d zones", len(self._zones))

    def _load(self, path: Optional[str]) -> list:
        candidates = [
            path,
            os.path.join(os.path.dirname(__file__), "..", "..", "data", "taxi_zones.json"),
            "/app/data/taxi_zones.json",
        ]
        for p in candidates:
            if p and os.path.exists(p):
                try:
                    with open(p, encoding="utf-8") as f:
                        data = json.load(f)
                    log.info("Loaded taxi_zones.json from %s (%d zones)", p, len(data))
                    return data
                except Exception as exc:
                    log.warning("Failed to read %s: %s", p, exc)
        log.warning("taxi_zones.json not found — using 7-zone fallback")
        return _DEFAULT_ZONES

    def get(self, zone_id: int) -> Optional[Zone]:
        return self._by_id.get(zone_id)

    def get_or_random(self, zone_id: int) -> Zone:
        return self._by_id.get(zone_id) or self.random_zone()

    def random_zone(self) -> Zone:
        return random.choices(self._zones, weights=self._weights, k=1)[0]

    def random_pair(self) -> tuple[Zone, Zone]:
        """Return (pickup, dropoff) ensuring they are different zones."""
        pu = self.random_zone()
        candidates = [z for z in self._zones if z.zone_id != pu.zone_id]
        do = random.choice(candidates) if candidates else pu
        return pu, do

    @property
    def zones(self) -> List[Zone]:
        return self._zones

    def __len__(self) -> int:
        return len(self._zones)
