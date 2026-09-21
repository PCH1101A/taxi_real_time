import json
import math
import os
import random
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from config import config

def get_trip_waypoints(
    s_lat: float, s_lng: float, pu_b: str, t_lat: float, t_lng: float, do_b: str
) -> List[tuple[float, float]]:
    pu_b = (pu_b or "").strip()
    do_b = (do_b or "").strip()
    if pu_b == do_b:
        if pu_b == "Queens" and (s_lat < 40.60 or t_lat < 40.60) and abs(s_lat - t_lat) > 0.05:
            return [(s_lat, s_lng), (40.5980, -73.8180), (t_lat, t_lng)]
        if pu_b == "Manhattan" and abs(s_lng - t_lng) > 0.015:
            mid_lat = (s_lat + t_lat) * 0.5
            mid_lng = max(-74.015, min(-73.935, (s_lng + t_lng) * 0.5))
            return [(s_lat, s_lng), (mid_lat, mid_lng), (t_lat, t_lng)]
        return [(s_lat, s_lng), (t_lat, t_lng)]

    waypoints: List[tuple[float, float]] = [(s_lat, s_lng)]
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
        if avg_lat <= 40.710:
            waypoints.append((40.7070, -73.9930))
        elif avg_lat <= 40.735:
            waypoints.append((40.7135, -73.9723))
        else:
            waypoints.extend([(40.7570, -73.9542), (40.7380, -73.9535)])
    elif is_m_q:
        if avg_lat < 40.748:
            waypoints.append((40.7445, -73.9635))
        elif avg_lat < 40.780:
            waypoints.append((40.7570, -73.9542))
        else:
            waypoints.append((40.7760, -73.9240))
    elif is_m_bx:
        if avg_lat < 40.825:
            waypoints.append((40.8105, -73.9315))
        elif avg_lat < 40.855:
            waypoints.append((40.8285, -73.9335))
        else:
            waypoints.append((40.8730, -73.9110))
    elif is_b_q:
        if avg_lat > 40.725 and (s_lng < -73.94 or t_lng < -73.94):
            waypoints.append((40.7380, -73.9535))
    elif is_b_si:
        waypoints.append((40.6066, -74.0447))
    elif is_m_si:
        waypoints.extend([(40.6958, -74.0135), (40.6066, -74.0447)])
    elif is_q_bx:
        bridge = (40.7850, -73.9150) if avg_lat > 40.77 and s_lng < -73.88 else (40.8035, -73.8300)
        waypoints.append(bridge)
    elif is_ewr:
        bridge = (40.7262, -74.0180) if avg_lat < 40.745 else (40.7600, -74.0040)
        waypoints.append(bridge)
    else:
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
    waypoints: List[tuple[float, float]],
    progress: float,
    jitter: tuple[float, float] = (0.0, 0.0),
) -> tuple[float, float]:
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
    def __init__(self, zones_data_path: str = None):
        path = zones_data_path or config.DATA_PATH
        if not os.path.isabs(path) and not os.path.exists(path):
            alt_path = os.path.join(os.path.dirname(__file__), "..", "data", "taxi_zones.json")
            if os.path.exists(alt_path):
                path = alt_path

        try:
            with open(path, "r", encoding="utf-8") as f:
                self.zones: List[Dict] = json.load(f)
        except Exception as e:
            self.zones = [
                {"zone_id": 132, "borough": "Queens", "zone_name": "JFK Airport", "lat": 40.6413, "lng": -73.7781, "base_demand": 2.5},
                {"zone_id": 230, "borough": "Manhattan", "zone_name": "Times Sq/Theatre District", "lat": 40.7589, "lng": -73.9851, "base_demand": 2.5},
                {"zone_id": 161, "borough": "Manhattan", "zone_name": "Midtown Center", "lat": 40.7550, "lng": -73.9780, "base_demand": 2.2},
                {"zone_id": 234, "borough": "Manhattan", "zone_name": "Union Sq", "lat": 40.7360, "lng": -73.9905, "base_demand": 2.1},
                {"zone_id": 138, "borough": "Queens", "zone_name": "LaGuardia Airport", "lat": 40.7769, "lng": -73.8740, "base_demand": 2.3},
                {"zone_id": 87, "borough": "Manhattan", "zone_name": "Financial District North", "lat": 40.7090, "lng": -74.0090, "base_demand": 1.8},
                {"zone_id": 65, "borough": "Brooklyn", "zone_name": "Downtown Brooklyn/MetroTech", "lat": 40.6930, "lng": -73.9850, "base_demand": 1.4}
            ]

        self.zone_map: Dict[int, Dict] = {z["zone_id"]: z for z in self.zones}
        self.zone_weights = [z.get("base_demand", 1.0) for z in self.zones]
        self.active_trips: Dict[str, Dict] = {}

    def _calc_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        R = 3958.8  # Earth radius in miles
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        direct_miles = R * c
        return max(0.5, round(direct_miles * random.uniform(1.2, 1.45), 2))

    def create_new_trip(self, force_anomaly: bool = False, raw_parquet_row: Optional[Dict] = None) -> Dict:
        if raw_parquet_row:
            # Replay from actual TLC record
            pu_id = int(raw_parquet_row.get("PULocationID", 230))
            do_id = int(raw_parquet_row.get("DOLocationID", 161))
            pu_zone = self.zone_map.get(pu_id, random.choice(self.zones))
            do_zone = self.zone_map.get(do_id, random.choice(self.zones))
            
            trip_distance = float(raw_parquet_row.get("trip_distance", 2.0))
            if trip_distance <= 0:
                trip_distance = self._calc_distance(pu_zone["lat"], pu_zone["lng"], do_zone["lat"], do_zone["lng"])

            vendor_id = int(raw_parquet_row.get("VendorID", 2))
            passenger_count = int(raw_parquet_row.get("passenger_count", 1) or 1)
            rate_code_id = int(raw_parquet_row.get("RatecodeID", 1) or 1)
            payment_type = int(raw_parquet_row.get("payment_type", 1) or 1)
            
            fare_amount = float(raw_parquet_row.get("fare_amount", 15.0))
            extra = float(raw_parquet_row.get("extra", 1.0) or 0.0)
            mta_tax = float(raw_parquet_row.get("mta_tax", 0.5) or 0.5)
            tip_amount = float(raw_parquet_row.get("tip_amount", 3.0) or 0.0)
            tolls_amount = float(raw_parquet_row.get("tolls_amount", 0.0) or 0.0)
            improvement_surcharge = float(raw_parquet_row.get("improvement_surcharge", 1.0) or 1.0)
            congestion_surcharge = float(raw_parquet_row.get("congestion_surcharge", 2.5) or 2.5)
            airport_fee = float(raw_parquet_row.get("Airport_fee", 0.0) or 0.0)
            total_amount = float(raw_parquet_row.get("total_amount", fare_amount + tip_amount + 5.0))

        else:
            # Synthetic generation across full 265 zones
            pu_zone = random.choices(self.zones, weights=self.zone_weights, k=1)[0]
            do_candidates = [z for z in self.zones if z["zone_id"] != pu_zone["zone_id"]]
            do_zone = random.choice(do_candidates) if do_candidates else pu_zone
            pu_id = pu_zone["zone_id"]
            do_id = do_zone["zone_id"]

            trip_distance = self._calc_distance(pu_zone["lat"], pu_zone["lng"], do_zone["lat"], do_zone["lng"])
            vendor_id = random.choice([1, 2])
            passenger_count = random.choices([1, 2, 3, 4, 5, 6], weights=[65, 18, 7, 4, 4, 2], k=1)[0]
            rate_code_id = 1 if pu_id not in (132, 138, 1) else random.choice([1, 2, 3])
            payment_type = random.choices([1, 2, 3, 4], weights=[72, 25, 2, 1], k=1)[0]
            
            base_rate = round(3.00 + (trip_distance * 3.50), 2)
            fare_amount = round(base_rate, 2)

            extra = 1.00 if random.random() > 0.5 else 2.50
            mta_tax = 0.50
            tip_amount = round(fare_amount * random.choice([0.15, 0.20, 0.25, 0.0]), 2) if payment_type == 1 else 0.0
            tolls_amount = round(random.choice([0.0, 0.0, 6.94, 13.75]), 2) if trip_distance > 8.0 else 0.0
            improvement_surcharge = 1.00
            congestion_surcharge = 2.50 if pu_zone.get("borough") == "Manhattan" else 0.00
            airport_fee = 1.75 if pu_id in (132, 138) or do_id in (132, 138) else 0.00
            total_amount = round(fare_amount + extra + mta_tax + tip_amount + tolls_amount + improvement_surcharge + congestion_surcharge + airport_fee, 2)

        trip_id = f"tx-{uuid.uuid4().hex[:8]}"
        avg_speed = random.uniform(10.0, 24.0)
        est_duration_sec = max(12, int((trip_distance / avg_speed) * 3600 / 15))
        now_iso = datetime.now(timezone.utc).isoformat()

        trip_state = {
            # ── 19 TLC Canonical Columns ──
            "VendorID": vendor_id,
            "tpep_pickup_datetime": now_iso,
            "tpep_dropoff_datetime": None,
            "passenger_count": passenger_count,
            "trip_distance": trip_distance,
            "RatecodeID": rate_code_id,
            "store_and_fwd_flag": "N",
            "PULocationID": pu_id,
            "DOLocationID": do_id,
            "payment_type": payment_type,
            "fare_amount": fare_amount,
            "extra": extra,
            "mta_tax": mta_tax,
            "tip_amount": tip_amount,
            "tolls_amount": tolls_amount,
            "improvement_surcharge": improvement_surcharge,
            "total_amount": total_amount,
            "congestion_surcharge": congestion_surcharge,
            "Airport_fee": airport_fee,
            # ── Real-time Tracking Fields ──
            "trip_id": trip_id,
            "pickup_zone_name": pu_zone.get("zone_name", f"Zone {pu_id}"),
            "pickup_borough": pu_zone.get("borough", "Manhattan"),
            "dropoff_zone_name": do_zone.get("zone_name", f"Zone {do_id}"),
            "dropoff_borough": do_zone.get("borough", "Manhattan"),
            "current_zone_id": pu_id,
            "current_borough": pu_zone.get("borough", "Manhattan"),
            "start_lat": pu_zone.get("lat", 40.75),
            "start_lng": pu_zone.get("lng", -73.98),
            "target_lat": do_zone.get("lat", 40.75),
            "target_lng": do_zone.get("lng", -73.98),
            "waypoints": get_trip_waypoints(
                pu_zone.get("lat", 40.75),
                pu_zone.get("lng", -73.98),
                pu_zone.get("borough", "Manhattan"),
                do_zone.get("lat", 40.75),
                do_zone.get("lng", -73.98),
                do_zone.get("borough", "Manhattan"),
            ),
            "current_lat": pu_zone.get("lat", 40.75),
            "current_lng": pu_zone.get("lng", -73.98),
            "speed_mph": round(avg_speed, 1),
            "base_rate": base_rate,
            "progress_ratio": 0.0,
            "total_steps": max(3, int(est_duration_sec / 2)),
            "current_step": 0,
            "event_type": "TRIP_STARTED",
            "timestamp": time.time()
        }

        self.active_trips[trip_id] = trip_state
        return self._format_event(trip_state, "TRIP_STARTED")

    def step_trip(self, trip_id: str) -> Optional[Dict]:
        if trip_id not in self.active_trips:
            return None

        trip = self.active_trips[trip_id]
        trip["current_step"] += 1
        trip["progress_ratio"] = min(1.0, round(trip["current_step"] / trip["total_steps"], 2))
        
        r = trip["progress_ratio"]
        jitter = (random.uniform(-0.0003, 0.0003), random.uniform(-0.0003, 0.0003))
        waypoints = trip.get("waypoints") or [(trip["start_lat"], trip["start_lng"]), (trip["target_lat"], trip["target_lng"])]
        cur_lat, cur_lng = interpolate_polyline(waypoints, r, jitter)
        trip["current_lat"] = cur_lat
        trip["current_lng"] = cur_lng
        trip["speed_mph"] = round(max(5.0, trip["speed_mph"] + random.uniform(-2.0, 2.0)), 1)
        trip["timestamp"] = time.time()

        if trip["progress_ratio"] >= 1.0:
            trip["event_type"] = "TRIP_COMPLETED"
            trip["current_zone_id"] = trip["DOLocationID"]
            trip["current_borough"] = trip["dropoff_borough"]
            trip["tpep_dropoff_datetime"] = datetime.now(timezone.utc).isoformat()
            completed_event = self._format_event(trip, "TRIP_COMPLETED")
            del self.active_trips[trip_id]
            return completed_event
        else:
            trip["event_type"] = "LOCATION_PING"
            if r > 0.6:
                trip["current_zone_id"] = trip["DOLocationID"]
                trip["current_borough"] = trip["dropoff_borough"]
            return self._format_event(trip, "LOCATION_PING")

    def _format_event(self, trip: Dict, event_type: str) -> Dict:
        out = dict(trip)
        out["event_type"] = event_type
        out["datetime_utc"] = datetime.now(timezone.utc).isoformat()
        return out
