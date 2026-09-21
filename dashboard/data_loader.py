import json
import logging
from typing import Dict, List, Any, Optional
import redis
from config import config

log = logging.getLogger("dashboard.data_loader")

class RedisDataLoader:
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or config.REDIS_URL
        self._client: Optional[redis.Redis] = None

    def get_client(self) -> Optional[redis.Redis]:
        if self._client is None:
            try:
                self._client = redis.from_url(
                    self.redis_url, 
                    decode_responses=True, 
                    socket_connect_timeout=2,
                    socket_timeout=2
                )
                self._client.ping()
            except Exception as e:
                log.warning(f"Could not connect to Redis at {self.redis_url}: {e}")
                self._client = None
        return self._client

    def get_realtime_kpis(self) -> Dict[str, Any]:
        client = self.get_client()
        if not client:
            return {
                "total_active_vehicles": 0,
                "total_events_processed": 0,
                "last_density_update": 0
            }
        try:
            kpis = client.hgetall("hash:realtime_kpis")
            return {
                "total_active_vehicles": int(kpis.get("total_active_vehicles", 0)),
                "total_events_processed": int(kpis.get("total_events_processed", 0)),
                "last_density_update": float(kpis.get("last_density_update", 0))
            }
        except Exception as e:
            log.error(f"Error fetching realtime KPIs: {e}")
            return {
                "total_active_vehicles": 0,
                "total_events_processed": 0,
                "last_density_update": 0
            }

    def get_latest_density_metrics(self) -> Dict[str, Any]:
        client = self.get_client()
        if not client:
            return {}
        try:
            raw = client.get("kv:latest_density_metrics")
            if raw:
                return json.loads(raw)
        except Exception as e:
            log.error(f"Error fetching density metrics: {e}")
        return {}

    def get_taxi_zones_metadata(self) -> List[Dict[str, Any]]:
        if hasattr(self, "_cached_zones_metadata") and self._cached_zones_metadata:
            return self._cached_zones_metadata
        import os
        paths = [
            "/app/data/taxi_zones.json",
            os.path.join(os.path.dirname(__file__), "data", "taxi_zones.json"),
            os.path.join(os.path.dirname(__file__), "..", "data", "taxi_zones.json")
        ]
        for p in paths:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        self._cached_zones_metadata = json.load(f)
                        return self._cached_zones_metadata
                except Exception:
                    pass
        self._cached_zones_metadata = []
        return self._cached_zones_metadata

    def get_power_map_snapshot(self) -> Dict[str, Any]:
        """Fetch the latest Fleet Power Map snapshot (invasion_zones + territory_counts)."""
        client = self.get_client()
        if not client:
            return {"invasion_zones": [], "territory_counts": {}}
        try:
            raw = client.get("kv:power_map_snapshot")
            if raw:
                return json.loads(raw)
        except Exception as e:
            log.error(f"Error fetching power map snapshot: {e}")
        return {"invasion_zones": [], "territory_counts": {}}

data_loader = RedisDataLoader()

