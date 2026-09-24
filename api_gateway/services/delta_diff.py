"""Delta differential calculator for vehicle streaming.

Reduces payload sizes by tracking last-broadcasted vehicle coordinates
and returning only vehicles that moved significantly (> POSITION_THRESHOLD),
or full snapshots when requested.
"""
from typing import Dict, List, Tuple, Any

POSITION_THRESHOLD = 0.0001  # ~11 meters latitude/longitude change


class DeltaDiff:
    def __init__(self, threshold: float = POSITION_THRESHOLD):
        self.threshold = threshold
        self._cache: Dict[str, Tuple[float, float]] = {}

    def compute_delta(self, vehicles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter vehicles to only those whose positions have changed significantly since last frame."""
        changed: List[Dict[str, Any]] = []
        current_ids = set()

        for v in vehicles:
            tid = v.get("trip_id")
            if not tid:
                continue
            current_ids.add(tid)
            lat = float(v.get("lat", 0.0))
            lng = float(v.get("lng", 0.0))
            prev = self._cache.get(tid)

            if prev is None or (abs(prev[0] - lat) + abs(prev[1] - lng)) > self.threshold:
                changed.append(v)
                self._cache[tid] = (lat, lng)

        # Evict inactive vehicles from cache
        stale = [k for k in self._cache.keys() if k not in current_ids]
        for k in stale:
            del self._cache[k]

        return changed

    def reset(self):
        self._cache.clear()
