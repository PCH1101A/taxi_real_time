#!/usr/bin/env python3
"""
Precomputes real OpenStreetMap driving routes for NYC taxi zones and replaces
any artificial straight-line or low-bearing L-shape routes with true road centerlines.
"""
import concurrent.futures
import json
import math
import os
import sys
import time
import urllib.request
from typing import Dict, List, Tuple

def haversine_dist(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    d_lat = lat2 - lat1
    d_lng = (lng2 - lng1) * 0.76
    return math.hypot(d_lat, d_lng) * 69.0

def densify_path(points: List[Tuple[float, float]], max_step_miles: float = 0.04) -> List[Tuple[float, float]]:
    if len(points) <= 1:
        return points
    dense: List[Tuple[float, float]] = [points[0]]
    for i in range(len(points) - 1):
        p1 = points[i]
        p2 = points[i + 1]
        dist = haversine_dist(p1[0], p1[1], p2[0], p2[1])
        if dist <= max_step_miles:
            dense.append(p2)
            continue
        num_steps = max(2, int(math.ceil(dist / max_step_miles)))
        for step in range(1, num_steps + 1):
            frac = step / float(num_steps)
            lat = round(p1[0] + (p2[0] - p1[0]) * frac, 5)
            lng = round(p1[1] + (p2[1] - p1[1]) * frac, 5)
            dense.append((lat, lng))
    return dense

def fetch_osrm(pu_lng: float, pu_lat: float, do_lng: float, do_lat: float) -> List[Tuple[float, float]]:
    endpoints = [
        f"https://routing.openstreetmap.de/routed-car/route/v1/driving/{pu_lng},{pu_lat};{do_lng},{do_lat}?overview=full&geometries=geojson",
        f"https://router.project-osrm.org/route/v1/driving/{pu_lng},{pu_lat};{do_lng},{do_lat}?overview=full&geometries=geojson",
    ]
    for url in endpoints:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "NYCTaxiTelemetry/2.0"})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    if data.get("routes"):
                        coords = data["routes"][0]["geometry"]["coordinates"]
                        if len(coords) >= 2:
                            pts = [(round(c[1], 5), round(c[0], 5)) for c in coords]
                            return densify_path(pts)
        except Exception:
            continue
    return []

def main():
    cache_path = "simulator/road_routes_cache.json"
    zones_path = "data/taxi_zones.json"

    with open(cache_path, "r", encoding="utf-8") as f:
        routes: Dict[str, List[List[float]]] = json.load(f)

    with open(zones_path, "r", encoding="utf-8") as f:
        zones = json.load(f)

    zmap = {z["zone_id"]: z for z in zones}

    # Identify routes needing upgrade (short or low bearings)
    to_upgrade = []
    for k, pts in routes.items():
        if len(pts) <= 3:
            to_upgrade.append(k)
        else:
            b_set = set()
            for i in range(len(pts) - 1):
                b_set.add(round(math.atan2(pts[i+1][1]-pts[i][1], pts[i+1][0]-pts[i][0]), 2))
            if len(b_set) <= 4:
                to_upgrade.append(k)

    print(f"Total routes in cache: {len(routes)}. Routes to upgrade to real OSM roads: {len(to_upgrade)}")

    def worker(k: str):
        try:
            parts = k.split("_")
            pu_id, do_id = int(parts[0]), int(parts[1])
            pu = zmap.get(pu_id)
            do = zmap.get(do_id)
            if not pu or not do:
                return k, None
            pts = fetch_osrm(pu["lng"], pu["lat"], do["lng"], do["lat"])
            return k, pts
        except Exception as e:
            return k, None

    success = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        future_map = {executor.submit(worker, k): k for k in to_upgrade}
        done_count = 0
        for future in concurrent.futures.as_completed(future_map):
            done_count += 1
            k, pts = future.result()
            if pts and len(pts) >= 4:
                routes[k] = [[p[0], p[1]] for p in pts]
                success += 1
            if done_count % 100 == 0 or done_count == len(to_upgrade):
                print(f"Progress: {done_count}/{len(to_upgrade)} processed, {success} upgraded.")

    print(f"Saving upgraded cache with {len(routes)} routes ({success} newly replaced with true OSM streets)...")
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(routes, f, separators=(",", ":"))
    print("Done! Cache saved.")

if __name__ == "__main__":
    main()
