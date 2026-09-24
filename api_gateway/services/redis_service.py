"""Async Redis Service with background cache polling & subscriber fan-out."""
import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional, Set
from fastapi import WebSocket
import redis.asyncio as aioredis

log = logging.getLogger("api_gateway.redis_service")


class RedisService:
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._client: Optional[aioredis.Redis] = None
        self._polling_task: Optional[asyncio.Task] = None
        self._running = False

        # In-memory cached state
        self.last_kpi_frame: Dict[str, Any] = {
            "total_active_vehicles": 0,
            "total_events_processed": 0,
            "last_density_update": 0.0,
            "engine": "Apache Flink",
        }
        self.last_fleet_frame: Dict[str, Any] = {
            "timestamp": 0.0,
            "total_active_vehicles": 0,
            "taxi_type_distribution": {},
            "borough_distribution": {},
            "vehicles": [],
            "top_congested_zones": [],
            "all_zones": [],
            "territory_counts": {},
            "invasion_zones": [],
            "total_fare_in_flight": 0.0,
            "average_speed_mph": 0.0,
        }

        # Active WebSocket connections
        self.fleet_subscribers: Set[WebSocket] = set()
        self.kpi_subscribers: Set[WebSocket] = set()

    async def get_client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = aioredis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
        return self._client

    async def fetch_realtime_kpis(self) -> Dict[str, Any]:
        """Fetch realtime KPIs from Redis hash:realtime_kpis."""
        try:
            client = await self.get_client()
            kpis = await client.hgetall("hash:realtime_kpis")
            if kpis:
                return {
                    "total_active_vehicles": int(kpis.get("total_active_vehicles", 0)),
                    "total_events_processed": int(kpis.get("total_events_processed", 0)),
                    "last_density_update": float(kpis.get("last_density_update", 0.0)),
                    "engine": kpis.get("engine", "Apache Flink"),
                }
        except Exception as e:
            log.warning(f"Error reading hash:realtime_kpis: {e}")
        return self.last_kpi_frame

    async def fetch_density_metrics(self) -> Dict[str, Any]:
        """Fetch density metrics from Redis kv:latest_density_metrics."""
        try:
            client = await self.get_client()
            raw = await client.get("kv:latest_density_metrics")
            if raw:
                return json.loads(raw)
        except Exception as e:
            log.warning(f"Error reading kv:latest_density_metrics: {e}")
        return {}

    async def fetch_power_map_snapshot(self) -> Dict[str, Any]:
        """Fetch Fleet Power Map snapshot from Redis kv:power_map_snapshot."""
        try:
            client = await self.get_client()
            raw = await client.get("kv:power_map_snapshot")
            if raw:
                return json.loads(raw)
        except Exception as e:
            log.warning(f"Error reading kv:power_map_snapshot: {e}")
        return {"invasion_zones": [], "territory_counts": {}}

    async def register_fleet_ws(self, ws: WebSocket):
        self.fleet_subscribers.add(ws)

    async def unregister_fleet_ws(self, ws: WebSocket):
        self.fleet_subscribers.discard(ws)

    async def register_kpi_ws(self, ws: WebSocket):
        self.kpi_subscribers.add(ws)

    async def unregister_kpi_ws(self, ws: WebSocket):
        self.kpi_subscribers.discard(ws)

    async def broadcast_to_group(self, subscribers: Set[WebSocket], message: str):
        if not subscribers:
            return
        dead: List[WebSocket] = []
        for ws in subscribers:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            subscribers.discard(ws)

    async def _poll_loop(self):
        log.info("Starting Redis polling loop (2.0s cycle)...")
        while self._running:
            try:
                # 1. Fetch KPI hash
                kpi_data = await self.fetch_realtime_kpis()
                self.last_kpi_frame = kpi_data
                kpi_json = json.dumps(kpi_data)
                await self.broadcast_to_group(self.kpi_subscribers, kpi_json)

                # 2. Fetch Density Metrics
                density_raw = await self.fetch_density_metrics()
                if density_raw:
                    # Check power map fallback
                    territory = density_raw.get("territory_counts")
                    invasion = density_raw.get("invasion_zones")
                    if not territory or not invasion:
                        power_snap = await self.fetch_power_map_snapshot()
                        territory = territory or power_snap.get("territory_counts", {})
                        invasion = invasion or power_snap.get("invasion_zones", [])

                    vehicles = density_raw.get("active_vehicles_sample", [])
                    fleet_frame = {
                        "timestamp": density_raw.get("timestamp", 0.0),
                        "total_active_vehicles": density_raw.get("total_active_vehicles", len(vehicles)),
                        "taxi_type_distribution": density_raw.get("taxi_type_distribution", {}),
                        "borough_distribution": density_raw.get("borough_distribution", {}),
                        "vehicles": vehicles,
                        "top_congested_zones": density_raw.get("top_congested_zones", []),
                        "all_zones": density_raw.get("all_zones", []),
                        "territory_counts": territory,
                        "invasion_zones": invasion,
                        "total_fare_in_flight": density_raw.get("total_fare_in_flight", 0.0),
                        "average_speed_mph": density_raw.get("average_speed_mph", 0.0),
                    }
                    self.last_fleet_frame = fleet_frame
                    fleet_json = json.dumps(fleet_frame)
                    await self.broadcast_to_group(self.fleet_subscribers, fleet_json)
            except Exception as e:
                log.error(f"Error in Redis poller loop: {e}", exc_info=True)

            await asyncio.sleep(2.0)

    async def start(self):
        self._running = True
        self._polling_task = asyncio.create_task(self._poll_loop())

    async def stop(self):
        self._running = False
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
        if self._client:
            await self._client.aclose()


redis_service = RedisService()
