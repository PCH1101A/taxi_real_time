"""REST API router for snapshot queries and OSRM route proxying."""
import logging
from typing import Any, Dict, List
from fastapi import APIRouter, Query
import httpx
from services.redis_service import redis_service

router = APIRouter()
log = logging.getLogger("api_gateway.rest_api")

# Memory cache for routes: key: (s_lng, s_lat, t_lng, t_lat) -> payload
_ROUTE_CACHE: Dict[str, Dict[str, Any]] = {}


def _fallback_nyc_corridor_route(s_lng: float, s_lat: float, t_lng: float, t_lat: float) -> List[List[float]]:
    """Generate realistic land/bridge corridor waypoints to avoid straight lines cutting across rivers/bays."""
    def _guess_borough(lng: float, lat: float) -> str:
        if lng < -74.05:
            return "Staten Island"
        if lat >= 40.795 and lng > -73.93:
            return "Bronx"
        if lng > -73.93:
            return "Queens" if lat >= 40.70 else "Brooklyn"
        if -74.025 <= lng <= -73.925 and 40.70 <= lat <= 40.88:
            return "Manhattan"
        return "Brooklyn"

    pu_b = _guess_borough(s_lng, s_lat)
    do_b = _guess_borough(t_lng, t_lat)
    avg_lat = (s_lat + t_lat) / 2.0

    pts: List[List[float]] = [[s_lng, s_lat]]

    if ("Staten Island" in (pu_b, do_b)) and (pu_b != do_b):
        if pu_b == "Staten Island":
            pts.extend([[-74.1200, 40.6120], [-74.0447, 40.6066], [-74.0150, 40.6450]])
        else:
            pts.extend([[-74.0150, 40.6450], [-74.0447, 40.6066], [-74.1200, 40.6120]])

    elif ("Manhattan" in (pu_b, do_b)) and ("Brooklyn" in (pu_b, do_b)):
        if avg_lat <= 40.715:
            pts.append([-73.9930, 40.7070])  # Brooklyn / Manhattan Bridge
        elif avg_lat <= 40.735:
            pts.append([-73.9723, 40.7135])  # Williamsburg Bridge
        else:
            pts.extend([[-73.9542, 40.7570], [-73.9535, 40.7380]])  # Queensboro + Pulaski

    elif ("Manhattan" in (pu_b, do_b)) and ("Queens" in (pu_b, do_b)):
        if avg_lat < 40.750:
            pts.append([-73.9635, 40.7445])  # Queens-Midtown Tunnel
        elif avg_lat < 40.780:
            pts.append([-73.9542, 40.7570])  # Queensboro Bridge
        else:
            pts.append([-73.9240, 40.7760])  # RFK / Triborough Bridge

    elif ("Manhattan" in (pu_b, do_b)) and ("Bronx" in (pu_b, do_b)):
        pts.append([-73.9315, 40.8105])  # 3rd Ave / Willis Bridge

    elif ("Queens" in (pu_b, do_b)) and ("Bronx" in (pu_b, do_b)):
        pts.append([-73.8300, 40.8035])  # Bronx-Whitestone Bridge

    elif pu_b == "Manhattan" and do_b == "Manhattan":
        mid_lat = (s_lat + t_lat) * 0.5
        mid_lng = max(-74.015, min(-73.935, (s_lng + t_lng) * 0.5))
        pts.append([mid_lng, mid_lat])

    pts.append([t_lng, t_lat])
    return pts


@router.get("/api/v1/density")
async def get_density():
    """Return the latest density snapshot."""
    if redis_service.last_fleet_frame.get("vehicles"):
        return redis_service.last_fleet_frame
    return await redis_service.fetch_density_metrics()


@router.get("/api/v1/kpis")
async def get_kpis():
    """Return the latest KPI snapshot."""
    if redis_service.last_kpi_frame.get("total_active_vehicles"):
        return redis_service.last_kpi_frame
    return await redis_service.fetch_realtime_kpis()


@router.get("/api/v1/route")
async def get_route(
    s_lng: float = Query(..., description="Start Longitude"),
    s_lat: float = Query(..., description="Start Latitude"),
    t_lng: float = Query(..., description="Target Longitude"),
    t_lat: float = Query(..., description="Target Latitude"),
):
    """Proxy OSRM driving routes with NYC bridge fallback & memory caching."""
    s_lng_r, s_lat_r = round(s_lng, 5), round(s_lat, 5)
    t_lng_r, t_lat_r = round(t_lng, 5), round(t_lat, 5)
    cache_key = f"{s_lng_r},{s_lat_r}->{t_lng_r},{t_lat_r}"

    if cache_key in _ROUTE_CACHE:
        return _ROUTE_CACHE[cache_key]

    # Minimal distance check
    if abs(s_lng_r - t_lng_r) < 0.0001 and abs(s_lat_r - t_lat_r) < 0.0001:
        res = {
            "coordinates": [[s_lng_r, s_lat_r], [t_lng_r, t_lat_r]],
            "optimal_distance_miles": 0.5,
            "est_duration_min": 1.0,
        }
        _ROUTE_CACHE[cache_key] = res
        return res

    endpoints = [
        f"https://routing.openstreetmap.de/routed-car/route/v1/driving/{s_lng_r},{s_lat_r};{t_lng_r},{t_lat_r}?overview=full&geometries=geojson",
        f"https://router.project-osrm.org/route/v1/driving/{s_lng_r},{s_lat_r};{t_lng_r},{t_lat_r}?overview=full&geometries=geojson",
    ]

    async with httpx.AsyncClient(timeout=2.0) as client:
        for url in endpoints:
            try:
                resp = await client.get(url, headers={"User-Agent": "NYCTaxiTelemetry/1.0"})
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("code") == "Ok" and data.get("routes"):
                        r0 = data["routes"][0]
                        coords = r0["geometry"]["coordinates"]
                        if len(coords) >= 2:
                            res = {
                                "coordinates": coords,
                                "optimal_distance_miles": round(r0.get("distance", 0) / 1609.34, 2),
                                "est_duration_min": round(r0.get("duration", 0) / 60.0, 1),
                            }
                            if len(_ROUTE_CACHE) > 5000:
                                _ROUTE_CACHE.clear()
                            _ROUTE_CACHE[cache_key] = res
                            return res
            except Exception as e:
                log.debug(f"OSRM endpoint {url} failed: {e}")
                continue

    # Fallback route
    corridor_pts = _fallback_nyc_corridor_route(s_lng_r, s_lat_r, t_lng_r, t_lat_r)
    dlat = abs(t_lat_r - s_lat_r) * 69.0
    dlng = abs(t_lng_r - s_lng_r) * 52.0
    approx_miles = max(0.5, round(dlat + dlng, 2))
    res = {
        "coordinates": corridor_pts,
        "optimal_distance_miles": approx_miles,
        "est_duration_min": round(approx_miles / 18.0 * 60, 1),
    }
    if len(_ROUTE_CACHE) > 5000:
        _ROUTE_CACHE.clear()
    _ROUTE_CACHE[cache_key] = res
    return res
