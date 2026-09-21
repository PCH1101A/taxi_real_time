import html
import json
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Any, Optional
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st
import streamlit.components.v1 as components
from streamlit_autorefresh import st_autorefresh

from config import config
from data_loader import data_loader

def _fallback_nyc_corridor_route(s_lng: float, s_lat: float, t_lng: float, t_lat: float) -> list:
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

    pts: list = [[s_lng, s_lat]]

    if ("Staten Island" in (pu_b, do_b)) and (pu_b != do_b):
        # Route via Verrazzano-Narrows Bridge & I-278 expressway corridor
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
        # Manhattan grid avenue turn
        mid_lat = (s_lat + t_lat) * 0.5
        mid_lng = max(-74.015, min(-73.935, (s_lng + t_lng) * 0.5))
        pts.append([mid_lng, mid_lat])

    pts.append([t_lng, t_lat])
    return pts


@st.cache_data(ttl=86400, max_entries=2000, show_spinner=False)
def fetch_driving_route(start_lng: float, start_lat: float, target_lng: float, target_lat: float) -> dict:
    """Ultra-fast driving route adhering strictly to real NYC street & bridge geometry with OSRM & smart fallback."""
    s_lng, s_lat = round(float(start_lng), 5), round(float(start_lat), 5)
    t_lng, t_lat = round(float(target_lng), 5), round(float(target_lat), 5)

    if abs(s_lng - t_lng) < 0.0001 and abs(s_lat - t_lat) < 0.0001:
        return {
            "coordinates": [[s_lng, s_lat], [t_lng, t_lat]],
            "optimal_distance_miles": 0.5,
            "est_duration_min": 1.0,
        }

    endpoints = [
        f"https://routing.openstreetmap.de/routed-car/route/v1/driving/{s_lng:.5f},{s_lat:.5f};{t_lng:.5f},{t_lat:.5f}?overview=full&geometries=geojson",
        f"https://router.project-osrm.org/route/v1/driving/{s_lng:.5f},{s_lat:.5f};{t_lng:.5f},{t_lat:.5f}?overview=full&geometries=geojson",
    ]

    for url in endpoints:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "NYCTaxiTelemetry/1.0"})
            with urllib.request.urlopen(req, timeout=2.0) as response:
                if response.status == 200:
                    res_data = json.loads(response.read().decode())
                    if res_data.get("code") == "Ok" and res_data.get("routes"):
                        r0 = res_data["routes"][0]
                        coords = r0["geometry"]["coordinates"]
                        if len(coords) >= 2:
                            opt_miles = round(r0.get("distance", 0) / 1609.34, 2)
                            dur_min = round(r0.get("duration", 0) / 60.0, 1)
                            return {
                                "coordinates": coords,
                                "optimal_distance_miles": opt_miles,
                                "est_duration_min": dur_min,
                            }
        except Exception:
            continue

    # Fallback to bridge-aware NYC highway & corridor polyline
    corridor_pts = _fallback_nyc_corridor_route(s_lng, s_lat, t_lng, t_lat)
    dlat = abs(t_lat - s_lat) * 69.0
    dlng = abs(t_lng - s_lng) * 52.0
    approx_miles = max(0.5, round(dlat + dlng, 2))
    return {
        "coordinates": corridor_pts,
        "optimal_distance_miles": approx_miles,
        "est_duration_min": round(approx_miles / 18.0 * 60, 1),
    }

def get_column_series(df: pd.DataFrame, col: str, default: Any = "") -> pd.Series:
    """Safely extract a pandas Series with fallback default if column does not exist."""
    if col in df.columns:
        return df[col].fillna(default)
    return pd.Series([default] * len(df), index=df.index)

def get_numeric_series(df: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    """Safely extract a numeric pandas Series with fallback default if column does not exist."""
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce").fillna(default)
    return pd.Series([default] * len(df), index=df.index)

def format_fleet_df(df: pd.DataFrame, color_mode: str = "TAXI_TYPE") -> pd.DataFrame:
    """High-performance vectorized telemetry standardization for PyDeck layers and tooltips."""
    if df is None or df.empty:
        return pd.DataFrame(columns=[
            "lat", "lng", "trip_id", "dataset_source", "taxi_type_name", "taxi_type_icon",
            "taxi_type_color_hex", "taxi_type_rgb", "zone_name", "borough", "speed_mph",
            "fare_amount", "passenger_count", "start_lat",
            "start_lng", "target_lat", "target_lng", "dropoff_zone_name",
            "dropoff_borough", "progress_ratio", "core_color",
            "lat_fmt", "lng_fmt", "speed_mph_fmt", "fare_amount_fmt",
            "progress_pct", "trip_distance_fmt",
            "optimal_distance_fmt", "efficiency_pct", "efficiency_badge",
            "efficiency_color", "efficiency_tag", "tooltip_html"
        ])
    df = df.copy()
    df["lng"] = pd.to_numeric(df["lng"], errors="coerce")
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df = df.dropna(subset=["lng", "lat"])
    if df.empty:
        return df

    # ── Map Taxi Types (Yellow / Green / FHVHV) ──
    ds_series = get_column_series(df, "dataset_source", "YELLOW").astype(str).str.upper()
    df["dataset_source"] = ds_series

    taxi_meta_map = {
        "GREEN": ("Green Boro Taxi", "🚕", "#22C55E", [34, 197, 94, 245]),
        "FHVHV": ("FHVHV (Uber/Lyft)", "📱", "#A855F7", [168, 85, 247, 245]),
    }
    default_meta = ("Yellow Cab", "🚖", "#FACC15", [250, 204, 21, 245])

    meta_tuples = [taxi_meta_map.get(ds, default_meta) for ds in ds_series]
    df["taxi_type_name"] = [m[0] for m in meta_tuples]
    df["taxi_type_icon"] = [m[1] for m in meta_tuples]
    df["taxi_type_color_hex"] = [m[2] for m in meta_tuples]
    df["taxi_type_rgb"] = [m[3] for m in meta_tuples]

    speed_series = get_numeric_series(df, "speed_mph", 15.0)
    df["speed_mph"] = speed_series

    if color_mode == "SPEED":
        def get_speed_color(spd):
            if spd >= 20.0: return [52, 211, 153, 245]
            if spd >= 10.0: return [251, 191, 36, 240]
            return [244, 63, 94, 255]
        df["core_color"] = [get_speed_color(s) for s in speed_series]
    else:
        df["core_color"] = df["taxi_type_rgb"]

    prog_series = get_numeric_series(df, "progress_ratio", 0.0)
    df["progress_ratio"] = prog_series
    df["progress_pct"] = (prog_series * 100).astype(int)

    df["lat_fmt"] = df["lat"].round(4).astype(str)
    df["lng_fmt"] = df["lng"].round(4).astype(str)
    df["speed_mph_fmt"] = speed_series.round(1).astype(str)

    fare_series = get_numeric_series(df, "total_amount", 0.0)
    if (fare_series == 0).all() and "fare_amount" in df.columns:
        fare_series = get_numeric_series(df, "fare_amount", 0.0)
    df["fare_amount"] = fare_series
    df["total_amount"] = fare_series
    df["fare_amount_fmt"] = fare_series.round(2).astype(str)

    df["passenger_count"] = get_numeric_series(df, "passenger_count", 1.0).astype(int)
    df["zone_name"] = get_column_series(df, "zone_name", "Origin")
    df["borough"] = get_column_series(df, "borough", "Manhattan")
    df["dropoff_zone_name"] = get_column_series(df, "dropoff_zone_name", "Destination")
    df["dropoff_borough"] = get_column_series(df, "dropoff_borough", "NYC")

    # ── Vectorized Route Efficiency & Detour Score ──
    act_dist = get_numeric_series(df, "trip_distance", 2.5)
    s_lat = get_numeric_series(df, "start_lat", 40.75)
    s_lng = get_numeric_series(df, "start_lng", -73.98)
    t_lat = get_numeric_series(df, "target_lat", 40.75)
    t_lng = get_numeric_series(df, "target_lng", -73.98)
    dlat = (t_lat - s_lat) * 69.0
    dlng = (t_lng - s_lng) * 52.0
    approx_opt = np.maximum(0.5, np.round(np.sqrt(dlat**2 + dlng**2) * 1.25, 2))

    if "optimal_distance_val" in df.columns:
        opt_dist = pd.to_numeric(df["optimal_distance_val"], errors="coerce").fillna(approx_opt)
    else:
        opt_dist = approx_opt

    eff_series = np.clip((opt_dist / np.maximum(0.5, act_dist) * 100).astype(int), 10, 100)
    df["efficiency_pct"] = eff_series
    df["optimal_distance_val"] = opt_dist
    df["optimal_distance_fmt"] = opt_dist.round(1).astype(str)
    df["trip_distance_fmt"] = act_dist.round(1).astype(str)

    def get_eff_meta(eff):
        if eff >= 90: return "🟢 OPTIMAL", "OPTIMAL", "#10B981"
        if eff >= 75: return "🟡 MODERATE DETOUR", "DETOUR", "#F59E0B"
        return "🔴 HIGH DETOUR", "INEFFICIENT", "#F43F5E"

    eff_metas = [get_eff_meta(e) for e in eff_series]
    df["efficiency_badge"] = [m[0] for m in eff_metas]
    df["efficiency_tag"] = [m[1] for m in eff_metas]
    df["efficiency_color"] = [m[2] for m in eff_metas]

    # ── High-Performance Lightweight Tooltip HTML ──
    tracked_id = None
    try:
        tracked_id = st.session_state.get("selected_trip_id")
    except Exception:
        pass

    records = df.to_dict("records")
    tooltips = []
    for r in records:
        tid = str(r["trip_id"])
        is_tracked = (tracked_id == tid)
        tt_hex = r["taxi_type_color_hex"]
        tt_icon = r["taxi_type_icon"]
        tt_name = r["taxi_type_name"]
        speed_val = float(r["speed_mph"])
        speed_col = "#34D399" if speed_val >= 18.0 else ("#FBBF24" if speed_val >= 10.0 else "#F43F5E")
        border_col = "#00F5FF" if is_tracked else tt_hex
        title_col = "#00F5FF" if is_tracked else "#F8FAFC"
        prog_pct = int(r["progress_pct"])

        tt = (
            f'<div style="font-family:\'JetBrains Mono\',monospace;padding:8px 10px;font-size:11px;color:#F8FAFC;background:rgba(11,17,32,0.96);border-radius:6px;border:1.5px solid {border_col};min-width:210px;pointer-events:none;user-select:none;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid rgba(255,255,255,0.1);padding-bottom:4px;margin-bottom:4px;">'
            f'<b style="color:{title_col};">{tt_icon} {tid}</b>'
            f'<span style="font-size:9px;color:{tt_hex};background:rgba(255,255,255,0.06);padding:1px 5px;border-radius:3px;">{tt_name}</span>'
            f'</div>'
            f'<div style="font-size:10px;line-height:1.3;margin-bottom:4px;">'
            f'<div>🟢 <b style="color:#38BDF8;">{r["zone_name"]}</b></div>'
            f'<div>🔴 <b style="color:#FB7185;">{r["dropoff_zone_name"]}</b></div>'
            f'</div>'
            f'<div style="display:flex;justify-content:space-between;background:rgba(15,23,42,0.7);padding:3px 6px;border-radius:4px;font-size:10px;">'
            f'<span>⚡ <b style="color:{speed_col};">{r["speed_mph_fmt"]} mph</b></span>'
            f'<span>💵 <b style="color:#FBBF24;">${r["fare_amount_fmt"]}</b></span>'
            f'<span>🎯 <b style="color:#38BDF8;">{prog_pct}%</b></span>'
            f'</div>'
            f'</div>'
        )
        tooltips.append(tt)
    df["tooltip_html"] = tooltips
    return df

# ── 1. Page Configuration & Theme ──────────────────────────────────────────
st.set_page_config(
    page_title="NYC Taxi Fleet Intelligence & Anomaly Radar",
    page_icon="🚖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 2. High-Tech Enterprise CSS Styling ────────────────────────────────────
st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

        html, body, [class*="css"] {
            font-family: 'Plus Jakarta Sans', sans-serif;
        }

        /* Top Operations Status Bar */
        .ops-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: linear-gradient(90deg, rgba(15, 23, 42, 0.95) 0%, rgba(30, 41, 59, 0.85) 100%);
            border: 1px solid rgba(56, 189, 248, 0.2);
            border-radius: 12px;
            padding: 10px 20px;
            margin-bottom: 16px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
        }
        .ops-title {
            font-size: 1.25rem;
            font-weight: 800;
            background: linear-gradient(90deg, #38BDF8 0%, #FBBF24 50%, #F43F5E 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.02em;
        }
        .ops-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(15, 23, 42, 0.8);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            padding: 4px 12px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.78rem;
            color: #E2E8F0;
        }
        .pulse-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: #10B981;
            box-shadow: 0 0 8px #10B981;
            animation: pulse 1.8s infinite;
        }
        @keyframes pulse {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
        }

        /* Metric Cards */
        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 14px;
            margin-bottom: 18px;
        }
        .kpi-card {
            background: linear-gradient(145deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.85) 100%);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 16px 18px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
            position: relative;
            overflow: hidden;
            transition: all 0.25s ease;
        }
        .kpi-card:hover {
            border-color: rgba(56, 189, 248, 0.4);
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(56, 189, 248, 0.15);
        }
        .kpi-card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 3px;
            background: linear-gradient(90deg, #38BDF8, #818CF8);
        }
        .kpi-card.danger::before {
            background: linear-gradient(90deg, #F43F5E, #FB7185);
        }
        .kpi-card.warning::before {
            background: linear-gradient(90deg, #F59E0B, #FBBF24);
        }
        .kpi-card.success::before {
            background: linear-gradient(90deg, #10B981, #34D399);
        }
        .kpi-label {
            color: #94A3B8;
            font-size: 0.76rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .kpi-number {
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.85rem;
            font-weight: 700;
            color: #F8FAFC;
            margin: 6px 0 2px 0;
            letter-spacing: -0.03em;
        }
        .kpi-subtext {
            font-size: 0.78rem;
            color: #64748B;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 4px;
        }

        /* Incident Feed Card */
        .incident-card {
            background: rgba(15, 23, 42, 0.75);
            border-radius: 10px;
            border-left: 4px solid #F43F5E;
            border-top: 1px solid rgba(255, 255, 255, 0.05);
            border-right: 1px solid rgba(255, 255, 255, 0.05);
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            padding: 12px 16px;
            margin-bottom: 10px;
            transition: transform 0.2s ease;
        }
        .incident-card:hover {
            transform: translateX(4px);
            background: rgba(30, 41, 59, 0.85);
        }
        .incident-card.high {
            border-left-color: #F59E0B;
        }
        .incident-card.warning {
            border-left-color: #EAB308;
        }
        .badge-tag {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.7rem;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 4px;
            text-transform: uppercase;
        }
        .badge-critical {
            background: rgba(244, 63, 94, 0.2);
            color: #FB7185;
            border: 1px solid rgba(244, 63, 94, 0.4);
        }
        .badge-high {
            background: rgba(245, 158, 11, 0.2);
            color: #FCD34D;
            border: 1px solid rgba(245, 158, 11, 0.4);
        }
        .badge-warning {
            background: rgba(234, 179, 8, 0.2);
            color: #FDE047;
            border: 1px solid rgba(234, 179, 8, 0.4);
        }

        /* Selected Driver Focus HUD & Card Highlight */
        .driver-focus-hud {
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.95) 0%, rgba(30, 41, 59, 0.9) 100%);
            border: 1.5px solid #38BDF8;
            border-radius: 12px;
            padding: 14px 18px;
            margin-bottom: 12px;
            box-shadow: 0 0 25px rgba(56, 189, 248, 0.25);
            position: relative;
        }
        .driver-focus-hud::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 3px;
            background: linear-gradient(90deg, #38BDF8, #F43F5E, #34D399);
        }
        .fleet-card-active {
            border: 1.5px solid #38BDF8 !important;
            background: rgba(14, 116, 144, 0.25) !important;
            box-shadow: 0 0 15px rgba(56, 189, 248, 0.3) !important;
        }

        /* Match 3D Map Height with Right Sidebar */
        [data-testid="stDeckGlJsonChart"], .stDeckGlJsonChart, .stDeckGlJsonChart > div, .stDeckGlJsonChart iframe {
            height: 760px !important;
            min-height: 760px !important;
        }

        /* Match 3D Map Height with Right Sidebar */
        [data-testid="stDeckGlJsonChart"], .stDeckGlJsonChart, .stDeckGlJsonChart > div, .stDeckGlJsonChart iframe {
            height: 760px !important;
            min-height: 760px !important;
        }

        /* Sleek Cyberpunk Scrollbar for Containers & Fleet List */
        ::-webkit-scrollbar {
            width: 6px;
            height: 6px;
        }
        ::-webkit-scrollbar-track {
            background: rgba(15, 23, 42, 0.6);
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb {
            background: rgba(56, 189, 248, 0.35);
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: rgba(56, 189, 248, 0.75);
        }
        [data-testid="stVerticalBlock"] {
            scrollbar-width: thin;
            scrollbar-color: rgba(56, 189, 248, 0.35) rgba(15, 23, 42, 0.6);
        }

        /* ── Balanced & Modern Sidebar Options ── */
        [data-testid="stSidebar"] {
            background-color: #0b1120 !important;
        }
        [data-testid="stSidebarContent"] {
            padding-top: 1.25rem !important;
            padding-bottom: 1.5rem !important;
            padding-left: 1.15rem !important;
            padding-right: 1.15rem !important;
        }
        [data-testid="stSidebar"] .stMarkdown h3 {
            font-size: 0.82rem !important;
            font-weight: 800 !important;
            color: #38BDF8 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.05em !important;
            margin-top: 0.9rem !important;
            margin-bottom: 0.45rem !important;
            padding-bottom: 0.25rem !important;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08) !important;
        }
        [data-testid="stSidebar"] hr {
            margin-top: 0.8rem !important;
            margin-bottom: 0.8rem !important;
            border-color: rgba(255, 255, 255, 0.08) !important;
        }
        [data-testid="stSidebar"] .stCheckbox {
            margin-bottom: -0.1rem !important;
            min-height: 2.0rem !important;
        }
        [data-testid="stSidebar"] .stCheckbox label span {
            font-size: 0.82rem !important;
            color: #E2E8F0 !important;
            font-weight: 500 !important;
        }
        [data-testid="stSidebar"] .stSelectbox, [data-testid="stSidebar"] .stMultiSelect {
            margin-bottom: 0.15rem !important;
        }
        [data-testid="stSidebar"] .stSelectbox label, [data-testid="stSidebar"] .stMultiSelect label, [data-testid="stSidebar"] .stSlider label {
            font-size: 0.78rem !important;
            font-weight: 600 !important;
            color: #94A3B8 !important;
            margin-bottom: 0.15rem !important;
        }
        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div {
            gap: 0.65rem !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── 3. Session State for Historical Time-Series Tracking & Selected Driver ──
if "history" not in st.session_state:
    st.session_state.history = {
        "timestamps": [],
        "active_vehicles": [],
        "moving_vehicles": [],
        "events_count": [],
        "throughput_rate": [],
        "avg_speed_history": [],
        "inflight_revenue_history": [],
        "tips_surcharges_history": [],
        "fare_velocity_history": [],
        "tips_velocity_history": [],
        "last_events_total": 0,
        "last_time": time.time()
    }

if "selected_trip_id" not in st.session_state:
    st.session_state.selected_trip_id = None

if "tracked_vehicle_cache" not in st.session_state:
    st.session_state.tracked_vehicle_cache = {}

# ── Handle Initial Deep-Link Query Params (Consume & Clear) ──
if "track_trip" in st.query_params:
    st.session_state.selected_trip_id = str(st.query_params["track_trip"])
    st.query_params.clear()

if "stop_track" in st.query_params:
    st.session_state.selected_trip_id = None
    st.session_state.tracked_vehicle_cache.clear()
    st.query_params.clear()

if "fleet_page" not in st.session_state:
    st.session_state.fleet_page = 1

# ── 4. Sidebar & Operations Center Controls ────────────────────────────────
with st.sidebar:
    st.markdown(
        """<div style="display:flex; align-items:center; gap:10px; margin-bottom:10px; padding:10px 12px; background:rgba(15,23,42,0.85); border:1px solid rgba(56,189,248,0.22); border-radius:10px;">
<img src="https://img.icons8.com/isometric/96/taxi.png" width="36"/>
<div>
<div style="font-weight:800; font-size:1.0rem; color:#F8FAFC; line-height:1.2;">NYC FLEET OPS</div>
<div style="font-size:0.7rem; color:#38BDF8; font-family:'JetBrains Mono',monospace; letter-spacing:0.04em;">REALTIME COMMAND</div>
</div>
</div>""",
        unsafe_allow_html=True,
    )
    
    st.markdown("### ⚙️ Stream Settings")
    auto_refresh = st.toggle("⚡ Auto-Refresh Stream", value=True)
    refresh_rate = st.slider("Interval (sec)", min_value=1, max_value=8, value=2, step=1, format="%d s")
    
    if auto_refresh:
        st_autorefresh(interval=refresh_rate * 1000, key="nyc_fleet_live_ticker")
    
    st.markdown("### 🎛️ Operations & Fleet Filter")
    selected_borough = st.selectbox(
        "NYC Borough",
        options=["All NYC", "Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island", "EWR"],
        index=0,
    )

    st.markdown("<div style='font-size:0.78rem; font-weight:700; color:#94A3B8; text-transform:uppercase; margin-top:8px; margin-bottom:4px;'>Taxi Fleet Types</div>", unsafe_allow_html=True)
    show_yellow = st.checkbox("🟡 Yellow Cab", value=True)
    show_green = st.checkbox("🟢 Green Taxi", value=True)
    show_fhvhv = st.checkbox("🟣 FHVHV (Uber/Lyft)", value=True)

    type_filter_map = {
        "YELLOW": show_yellow,
        "GREEN": show_green,
        "FHVHV": show_fhvhv,
    }
    allowed_sources = [k for k, v in type_filter_map.items() if v]
    color_mode = "TAXI_TYPE"

    st.markdown("### 🗺️ 3D Map Layers")
    layer_vehicles = st.checkbox("🚕 Real-Time Fleet Pins", value=True)
    layer_demand_heatmap = st.checkbox("🔥 Pickup Demand Heatmap", value=True)
    if layer_demand_heatmap:
        col_hm1, col_hm2 = st.columns(2)
        with col_hm1:
            heatmap_radius = st.slider("Heat Radius", min_value=30, max_value=130, value=75, step=5, help="Bán kính lan tỏa nhiệt điểm đón khách")
        with col_hm2:
            heatmap_intensity = st.slider("Glow Intensity", min_value=1.0, max_value=5.0, value=3.0, step=0.2, help="Cường độ phát sáng và tương phản màu nhiệt")
    else:
        heatmap_radius = 75
        heatmap_intensity = 3.0

    layer_busiest = st.checkbox("🔥 #1 Busiest Zone Radar", value=True)
    layer_airports = st.checkbox("✈️ Airport Hubs Radar", value=True)
    map_view_preset = st.selectbox(
        "Camera Focus Preset",
        [
            "NYC Overview (Zoomed)",
            "🔥 Manhattan Pickup Demand (Core)",
            "🔥 Focus #1 Busiest Zone",
            "Midtown & Times Square",
            "Downtown & Financial Hub",
            "✈️ Focus Airports (JFK & LGA)",
            "Brooklyn Hub"
        ]
    )

    client = data_loader.get_client()
    status_color = "#10B981" if client else "#F43F5E"
    status_text = "REDIS ONLINE" if client else "REDIS OFFLINE"
    st.markdown(
        f"""<div style="margin-top:16px; padding:10px 12px; background:rgba(15,23,42,0.7); border:1px solid rgba(255,255,255,0.08); border-radius:8px; font-size:0.75rem; color:#94A3B8; display:flex; justify-content:space-between; align-items:center;">
<span><span class="pulse-dot" style="display:inline-block; background-color:{status_color}; box-shadow:0 0 8px {status_color};"></span> <b style="color:{status_color}; font-size:0.78rem;">{status_text}</b></span>
<span><code>kafka:9092</code></span>
</div>""",
        unsafe_allow_html=True
    )

# ── 5. Data Ingestion & State Accumulation ─────────────────────────────────
kpis = data_loader.get_realtime_kpis()
density = data_loader.get_latest_density_metrics()
taxi_metadata = data_loader.get_taxi_zones_metadata()

all_zones = density.get("all_zones", [])
top_zones = density.get("top_congested_zones", [])
borough_dist = density.get("borough_distribution", {})
taxi_type_dist = density.get("taxi_type_distribution", {})
active_vehicles = density.get("active_vehicles_sample", [])
# Sanitize and filter out anomalous fare records (e.g. erroneous parquet charges)
active_vehicles = [
    v for v in active_vehicles
    if float(v.get("fare_amount", 0.0) or v.get("total_amount", 0.0) or 0.0) <= (100.0 if str(v.get("dataset_source", "")).upper() == "GREEN" else 200.0)
]

# Real-time counts for 3 taxi types
y_cnt = taxi_type_dist.get("YELLOW", sum(1 for v in active_vehicles if str(v.get("dataset_source", "")).upper() == "YELLOW"))
g_cnt = taxi_type_dist.get("GREEN", sum(1 for v in active_vehicles if str(v.get("dataset_source", "")).upper() == "GREEN"))
h_cnt = taxi_type_dist.get("FHVHV", sum(1 for v in active_vehicles if str(v.get("dataset_source", "")).upper() == "FHVHV"))

# ── Per-fleet aggregated metrics (for Tab 4 Fleet Analytics) ──────────────
_FLEET_KEYS = ["YELLOW", "GREEN", "FHVHV"]
_fleet_vehicles: dict[str, list] = {
    k: [v for v in active_vehicles if str(v.get("dataset_source", "")).upper() == k]
    for k in _FLEET_KEYS
}
fleet_stats: dict[str, dict] = {}
for _fk, _vlist in _fleet_vehicles.items():
    _speeds = [float(v.get("speed_mph",       0.0) or 0.0) for v in _vlist]
    _fares  = [float(v.get("fare_amount",      0.0) or 0.0) for v in _vlist]
    _tips   = [float(v.get("tip_amount",       0.0) or 0.0) for v in _vlist]
    _pax    = [int(  v.get("passenger_count",  1)   or 1)   for v in _vlist]
    fleet_stats[_fk] = {
        "count":      len(_vlist),
        "avg_speed":  round(sum(_speeds) / max(1, len(_speeds)), 1),
        "total_fare": round(sum(_fares),  2),
        "avg_fare":   round(sum(_fares)  / max(1, len(_fares)),  2),
        "total_tip":  round(sum(_tips),   2),
        "avg_tip":    round(sum(_tips)   / max(1, len(_tips)),   2),
        "total_pax":  sum(_pax),
        "avg_pax":    round(sum(_pax)    / max(1, len(_pax)),    2),
        "speeds_raw": _speeds,
    }

# ── Borough × Fleet matrix (for Tab 4 Heatmap) ────────────────────────────
_BOROUGH_ORDER = ["Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"]
borough_fleet_matrix: dict[str, dict] = {}
for _z in all_zones:
    _b  = _z.get("borough", "Unknown")
    _fb = _z.get("fleet_breakdown", {})
    if _b not in borough_fleet_matrix:
        borough_fleet_matrix[_b] = {"YELLOW": 0, "GREEN": 0, "FHVHV": 0, "total": 0}
    for _fk in _FLEET_KEYS:
        borough_fleet_matrix[_b][_fk] += int(_fb.get(_fk, 0))
    borough_fleet_matrix[_b]["total"] += int(_z.get("vehicle_count", 0))

# Rolling history calculation
now_ts = time.time()
dt_now = datetime.now(timezone.utc)
nyc_now = dt_now - timedelta(hours=4) # Approximate EDT

cur_events = kpis.get("total_events_processed", 0)
time_delta = max(0.5, now_ts - st.session_state.history["last_time"])
event_delta = max(0, cur_events - st.session_state.history["last_events_total"])
throughput = round(event_delta / time_delta, 1) if st.session_state.history["last_events_total"] > 0 else float(config.REFRESH_INTERVAL_MS / 1000 * 6.0)

# Real-time instantaneous speed & revenue metrics from current active vehicles
if active_vehicles:
    v_speeds = [float(v.get("speed_mph", 15.0)) for v in active_vehicles if pd.notnull(v.get("speed_mph"))]
    v_fares = [float(v.get("fare_amount", 0.0)) for v in active_vehicles if pd.notnull(v.get("fare_amount"))]
    v_tips = [float(v.get("tip_amount", 0.0) or (float(v.get("fare_amount", 0.0)) * 0.18)) for v in active_vehicles if pd.notnull(v.get("fare_amount"))]
    cur_avg_speed = round(sum(v_speeds) / max(1, len(v_speeds)), 1) if v_speeds else 16.5
    cur_inflight_fare = round(sum(v_fares), 2)
    cur_tips_surcharges = round(sum(v_tips), 2)
    cur_moving_cnt = sum(1 for s in v_speeds if s > 3.0)
    avg_unit_fare = cur_inflight_fare / max(1, len(v_fares))
    avg_unit_tip = cur_tips_surcharges / max(1, len(v_tips))
else:
    cur_avg_speed = 16.5
    cur_inflight_fare = 0.0
    cur_tips_surcharges = 0.0
    cur_moving_cnt = 0
    avg_unit_fare = 28.5
    avg_unit_tip = 5.2

# Dynamic real-time financial velocity ($/sec pulse synchronized with throughput waveform)
cur_fare_velocity = round(throughput * avg_unit_fare, 1)
cur_tips_velocity = round(throughput * avg_unit_tip, 1)

# Append to rolling buffer (retain 40 points)
st.session_state.history["timestamps"].append(dt_now.strftime("%H:%M:%S"))
st.session_state.history["active_vehicles"].append(kpis.get("total_active_vehicles", len(active_vehicles)))
st.session_state.history["moving_vehicles"].append(cur_moving_cnt)
st.session_state.history["events_count"].append(cur_events)
st.session_state.history["throughput_rate"].append(throughput)
st.session_state.history["avg_speed_history"].append(cur_avg_speed)
st.session_state.history["inflight_revenue_history"].append(cur_inflight_fare)
if "tips_surcharges_history" not in st.session_state.history:
    st.session_state.history["tips_surcharges_history"] = []
st.session_state.history["tips_surcharges_history"].append(cur_tips_surcharges)

if "fare_velocity_history" not in st.session_state.history:
    st.session_state.history["fare_velocity_history"] = []
st.session_state.history["fare_velocity_history"].append(cur_fare_velocity)

if "tips_velocity_history" not in st.session_state.history:
    st.session_state.history["tips_velocity_history"] = []
st.session_state.history["tips_velocity_history"].append(cur_tips_velocity)

st.session_state.history["last_events_total"] = cur_events
st.session_state.history["last_time"] = now_ts

# Keep buffer size <= 40
max_buf = 40
for k in ["timestamps", "active_vehicles", "moving_vehicles", "events_count", "throughput_rate", "avg_speed_history", "inflight_revenue_history", "tips_surcharges_history", "fare_velocity_history", "tips_velocity_history"]:
    if k not in st.session_state.history:
        st.session_state.history[k] = []
    if len(st.session_state.history[k]) > max_buf:
        st.session_state.history[k] = st.session_state.history[k][-max_buf:]

# ── 6. Header Operations Status & KPI Definitions (Used in Telemetry Tab) ──────
top_congested_name = top_zones[0]["zone_name"] if top_zones else "Initializing..."
top_congested_count = top_zones[0]["vehicle_count"] if top_zones else 0
top_congested_borough = top_zones[0].get("borough", "Manhattan") if top_zones else "NYC"

ops_bar_html = f"""
<div class="ops-bar" style="margin-top: 4px; margin-bottom: 12px;">
    <div style="display:flex; align-items:center; gap:12px;">
        <span class="pulse-dot"></span>
        <span class="ops-title">NYC TLC REAL-TIME FLEET INTELLIGENCE & POWER MAP</span>
    </div>
    <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
        <div class="ops-pill" style="border-color: rgba(250, 204, 21, 0.4); color: #FACC15;">🚖 <b>{y_cnt}</b> Yellow</div>
        <div class="ops-pill" style="border-color: rgba(34, 197, 94, 0.4); color: #22C55E;">🚕 <b>{g_cnt}</b> Green</div>
        <div class="ops-pill" style="border-color: rgba(168, 85, 247, 0.4); color: #C084FC;">📱 <b>{h_cnt}</b> FHVHV</div>
        <div class="ops-pill">🗽 NYC EDT: <b>{nyc_now.strftime('%H:%M:%S')}</b></div>
        <div class="ops-pill">🕒 UTC: <b>{dt_now.strftime('%H:%M:%S')}</b></div>
        <div class="ops-pill" style="border-color: rgba(16, 185, 129, 0.4); color: #34D399;">⚡ <b>{throughput}</b> EVT/S</div>
    </div>
</div>
"""

kpi_html = f"""
<div class="kpi-grid" style="margin-bottom: 16px;">
    <div class="kpi-card success">
        <div class="kpi-label">
            <span>🚕 Active Fleet (3 Types)</span>
            <span>🟢 ACTIVE</span>
        </div>
        <div class="kpi-number">{kpis['total_active_vehicles']:,}</div>
        <div class="kpi-subtext">
            <span>🟡 <b>{y_cnt}</b> Yellow &bull; 🟢 <b>{g_cnt}</b> Green &bull; 🟣 <b>{h_cnt}</b> FHVHV</span>
        </div>
    </div>
    <div class="kpi-card info">
        <div class="kpi-label">
            <span>💰 In-Flight Fare Flow</span>
            <span>💵 REVENUE</span>
        </div>
        <div class="kpi-number">${cur_inflight_fare:,.2f}</div>
        <div class="kpi-subtext">
            <span>Speed: <b>{cur_avg_speed:.1f} mph</b> &bull; Avg: <b>${cur_inflight_fare / max(1, len(active_vehicles)):.1f}</b>/trip</span>
        </div>
    </div>
    <div class="kpi-card">
        <div class="kpi-label">
            <span>⚡ Stream Events Processed</span>
            <span>KAFKA 3.8</span>
        </div>
        <div class="kpi-number">{kpis['total_events_processed']:,}</div>
        <div class="kpi-subtext">
            <span>Throughput: ~{throughput} events/sec</span>
        </div>
    </div>
    <div class="kpi-card warning">
        <div class="kpi-label">
            <span>🔥 Top Congestion Hotspot</span>
            <span>CONGESTION</span>
        </div>
        <div class="kpi-number" style="font-size: 1.25rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="{top_congested_name}">
            {top_congested_name}
        </div>
        <div class="kpi-subtext">
            <span>{top_congested_borough} • <b>{top_congested_count}</b> vehicles active</span>
        </div>
    </div>
</div>
"""

# ── 8. Main Multi-Tab Operations View ──────────────────────────────────────
# Fetch power map snapshot (invasion_zones + territory_counts from Welford tracker)
power_map_data = data_loader.get_power_map_snapshot()

tab1, tab2, tab3, tab4 = st.tabs([
    "🗺️ 3D Fleet Command Map",
    "📈 Live Stream Telemetry & Trends",
    "⚔️ Fleet Power Map",
    "📊 Fleet Analytics",
])

# ── TAB 1: 3D Fleet Command Map ───────────────────────────────────────────
with tab1:
    # Filter datasets
    df_v = pd.DataFrame(active_vehicles) if active_vehicles else pd.DataFrame(columns=["lat", "lng", "trip_id", "dataset_source", "zone_name", "borough", "speed_mph", "fare_amount", "passenger_count", "start_lat", "start_lng", "target_lat", "target_lng", "dropoff_zone_name", "dropoff_borough", "progress_ratio"])
    df_z = pd.DataFrame(all_zones) if all_zones else pd.DataFrame(columns=["lat", "lng", "zone_name", "borough", "vehicle_count", "congestion_level"])

    if not df_v.empty:
        df_v["dataset_source"] = get_column_series(df_v, "dataset_source", "YELLOW").astype(str).str.upper()
        if allowed_sources:
            df_v = df_v[df_v["dataset_source"].isin(allowed_sources)]
        else:
            df_v = df_v.iloc[0:0]

    if selected_borough != "All NYC":
        if not df_v.empty:
            df_v = df_v[df_v["borough"] == selected_borough]
        if not df_z.empty:
            df_z = df_z[df_z["borough"] == selected_borough]

    # Map presets with clearer zoom and focus
    preset_coords = {
        "NYC Overview (Zoomed)": {"lat": 40.7420, "lng": -73.9700, "zoom": 11.8, "pitch": 45},
        "NYC Overview": {"lat": 40.7420, "lng": -73.9700, "zoom": 11.8, "pitch": 45},
        "🔥 Manhattan Pickup Demand (Core)": {"lat": 40.7580, "lng": -73.9855, "zoom": 13.5, "pitch": 50},
        "Midtown & Times Square": {"lat": 40.7589, "lng": -73.9851, "zoom": 14.2, "pitch": 48},
        "Downtown & Financial Hub": {"lat": 40.7128, "lng": -74.0060, "zoom": 14.0, "pitch": 48},
        "✈️ Focus Airports (JFK & LGA)": {"lat": 40.7050, "lng": -73.8300, "zoom": 12.0, "pitch": 45},
        "Brooklyn Hub": {"lat": 40.6782, "lng": -73.9442, "zoom": 12.8, "pitch": 42},
    }

    borough_preset_coords = {
        "Manhattan": {"lat": 40.7831, "lng": -73.9712, "zoom": 12.6, "pitch": 48},
        "Brooklyn": {"lat": 40.6782, "lng": -73.9442, "zoom": 12.4, "pitch": 45},
        "Queens": {"lat": 40.7282, "lng": -73.7949, "zoom": 11.8, "pitch": 45},
        "Bronx": {"lat": 40.8448, "lng": -73.8648, "zoom": 12.4, "pitch": 45},
        "Staten Island": {"lat": 40.5795, "lng": -74.1502, "zoom": 11.6, "pitch": 45},
        "EWR": {"lat": 40.6895, "lng": -74.1745, "zoom": 13.0, "pitch": 45},
    }
    
    # Calculate live airport counts across active telemetry
    jfk_cnt = sum(1 for v in active_vehicles if v.get("zone_id") == 132 or "jfk" in str(v.get("zone_name", "")).lower() or "jfk" in str(v.get("dropoff_zone_name", "")).lower())
    lga_cnt = sum(1 for v in active_vehicles if v.get("zone_id") == 138 or "laguardia" in str(v.get("zone_name", "")).lower() or "laguardia" in str(v.get("dropoff_zone_name", "")).lower())
    ewr_cnt = sum(1 for v in active_vehicles if v.get("zone_id") == 1 or "newark" in str(v.get("zone_name", "")).lower() or "newark" in str(v.get("dropoff_zone_name", "")).lower())
    total_airport_taxis = jfk_cnt + lga_cnt + ewr_cnt

    # Top Busiest Hotspot zone
    busiest_zone = top_zones[0] if top_zones else None
    
    # Dynamic camera preset selection
    if map_view_preset == "🔥 Focus #1 Busiest Zone" and busiest_zone and pd.notnull(busiest_zone.get("lat")):
        cur_preset = {"lat": float(busiest_zone["lat"]), "lng": float(busiest_zone["lng"]), "zoom": 14.5, "pitch": 52}
    elif selected_borough != "All NYC" and map_view_preset == "NYC Overview (Zoomed)" and selected_borough in borough_preset_coords:
        cur_preset = borough_preset_coords[selected_borough]
    elif map_view_preset in preset_coords:
        cur_preset = preset_coords[map_view_preset]
    else:
        cur_preset = preset_coords["NYC Overview (Zoomed)"]

    # Check if a vehicle is currently selected for tracking (check all active_vehicles first)
    selected_veh = None
    is_trip_completed = False
    if st.session_state.selected_trip_id:
        target_id = str(st.session_state.selected_trip_id)
        matched_list = [v for v in active_vehicles if str(v.get("trip_id")) == target_id]
        if matched_list:
            veh_dict = dict(matched_list[0])
            st.session_state.tracked_vehicle_cache[target_id] = veh_dict
            selected_veh = pd.Series(veh_dict)
            is_trip_completed = (float(veh_dict.get("progress_ratio", 0.0) or 0.0) >= 1.0)
        elif target_id in st.session_state.tracked_vehicle_cache:
            # Persistent memory: keep vehicle tracked even if trip completed or drops from sample window
            veh_dict = dict(st.session_state.tracked_vehicle_cache[target_id])
            veh_dict["progress_ratio"] = 1.0
            veh_dict["speed_mph"] = 0.0
            selected_veh = pd.Series(veh_dict)
            is_trip_completed = True
        elif not df_v.empty:
            match = df_v[df_v["trip_id"].astype(str) == target_id]
            if not match.empty:
                veh_dict = match.iloc[0].to_dict()
                st.session_state.tracked_vehicle_cache[target_id] = veh_dict
                selected_veh = match.iloc[0]
                is_trip_completed = (float(veh_dict.get("progress_ratio", 0.0) or 0.0) >= 1.0)

    # Ensure tracked vehicle is never pruned out of df_v by borough or taxi type filters
    if selected_veh is not None:
        sel_tid = str(selected_veh.get("trip_id"))
        if df_v.empty or not (df_v["trip_id"].astype(str) == sel_tid).any():
            df_v = pd.concat([pd.DataFrame([selected_veh.to_dict()]), df_v], ignore_index=True)

    # Map vs Sidebar Layout - Expanded Map Width (3.8 : 1.2)
    map_col, right_col = st.columns([3.8, 1.2])

    with map_col:
        # Top Live Vehicle Tracking Banner HUD
        if selected_veh is not None:
            sel_tid = str(selected_veh.get("trip_id"))
            sel_c_icon = str(selected_veh.get("taxi_type_icon", "🚖"))
            sel_orig = str(selected_veh.get("zone_name", "Origin"))
            sel_dest = str(selected_veh.get("dropoff_zone_name", "Destination"))
            sel_prog = int(float(selected_veh.get("progress_ratio", 0.0) or 0.0) * 100)
            sel_spd = float(selected_veh.get("speed_mph", 15.0) or 15.0)
            sel_fare = float(selected_veh.get("fare_amount", 0.0) or 0.0)

            hud_bg = "rgba(16, 185, 129, 0.15)" if is_trip_completed else "rgba(0, 245, 255, 0.12)"
            hud_border = "#10B981" if is_trip_completed else "#00F5FF"
            hud_title = "🏁 TRIP COMPLETED (Arrived at Destination)" if is_trip_completed else "🎯 LIVE VEHICLE TRACKING ACTIVE"

            hud_c1, hud_c2 = st.columns([4.2, 1.1])
            with hud_c1:
                st.markdown(
                    f"""
                    <div style="background:{hud_bg}; border:1px solid {hud_border}66; border-radius:8px; padding:6px 12px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center; font-family:'JetBrains Mono',monospace; font-size:0.75rem; color:#F8FAFC;">
                        <span style="font-weight:800; color:{hud_border}; display:flex; align-items:center; gap:6px;">
                            <span class="pulse-dot" style="background:{hud_border}; box-shadow:0 0 8px {hud_border};"></span>
                            {hud_title}: <b>{sel_c_icon} {sel_tid}</b>
                        </span>
                        <span style="color:#CBD5E1;">{sel_orig} ➔ <b style="color:#FB7185;">{sel_dest}</b></span>
                        <span>⚡ <b>{sel_spd:.0f} mph</b> &bull; 🎯 <b>{sel_prog}%</b> &bull; 💵 <b>${sel_fare:.2f}</b></span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            with hud_c2:
                if st.button("🛑 Stop Track", key="hud_stop_track_btn", type="secondary", use_container_width=True):
                    st.session_state.selected_trip_id = None
                    st.session_state.tracked_vehicle_cache.clear()
                    st.query_params.clear()
                    st.rerun()

        deck_layers = []

        # 0. Pickup Demand Heatmap Layer (Bản đồ nhiệt mật độ khách đặt xe: Siêu nổi bật, phóng to sắc nét)
        df_v_fmt = format_fleet_df(df_v, color_mode=color_mode)
        if layer_demand_heatmap:
            heatmap_records = []
            
            # 0.1 Ingest vehicle pickup origins with dynamic demand weighting
            if not df_v_fmt.empty:
                v_dicts = df_v_fmt.to_dict("records")
                for r in v_dicts:
                    p_lng = float(r.get("start_lng") or r["lng"])
                    p_lat = float(r.get("start_lat") or r["lat"])
                    pax = int(r.get("passenger_count", 1) or 1)
                    fare = float(r.get("fare_amount", 10.0) or 10.0)
                    # Non-linear weighting for high pickup demand clusters
                    weight = (pax ** 0.6) * (1.2 + min(fare / 20.0, 2.5))
                    heatmap_records.append({"lng": p_lng, "lat": p_lat, "weight": weight})

            # 0.2 Ingest zone density telemetry to amplify active pickup demand clusters
            if not df_z.empty:
                z_dicts = df_z[["lng", "lat", "vehicle_count", "congestion_level"]].dropna(subset=["lng", "lat"]).to_dict("records")
                for z in z_dicts:
                    v_cnt = float(z.get("vehicle_count", 1) or 1)
                    c_level = str(z.get("congestion_level", "NORMAL"))
                    c_mult = 3.0 if "CRITICAL" in c_level else (2.0 if "HIGH" in c_level or "CONGESTED" in c_level else 1.2)
                    z_weight = max(1.0, v_cnt * 0.8 * c_mult)
                    heatmap_records.append({"lng": float(z["lng"]), "lat": float(z["lat"]), "weight": z_weight})

            if heatmap_records:
                heatmap_df = pd.DataFrame(heatmap_records)
                demand_heatmap_layer = pdk.Layer(
                    "HeatmapLayer",
                    id="pickup_demand_heatmap",
                    data=heatmap_df,
                    get_position=["lng", "lat"],
                    get_weight="weight",
                    radius_pixels=heatmap_radius,
                    intensity=heatmap_intensity,
                    threshold=0.02,
                    color_range=[
                        [14, 165, 233, 0],       # Transparent zero
                        [0, 240, 255, 170],      # Electric Cyan (Low demand / Normal flow)
                        [16, 185, 129, 215],     # Neon Emerald Green (Moderate demand)
                        [250, 204, 21, 240],     # Bright Yellow (High demand)
                        [249, 115, 22, 255],     # Vivid Amber Orange (High density)
                        [244, 63, 94, 255],      # Crimson Red (Peak hotspot)
                        [255, 255, 255, 255]     # Incandescent White Core (Extreme demand hub)
                    ],
                    pickable=False,
                )
                deck_layers.append(demand_heatmap_layer)

        # 1. Core Real-time Vehicle Pins Layer (Đội xe đang di chuyển - Tỉ lệ vừa vặn, sắc nét & Highlight khi trỏ chuột)
        if layer_vehicles and not df_v_fmt.empty:
            core_veh_layer = pdk.Layer(
                "ScatterplotLayer",
                id="fleet_vehicles",
                data=df_v_fmt,
                get_position=["lng", "lat"],
                get_fill_color="core_color",
                get_radius=50,
                radius_min_pixels=4.5,
                radius_max_pixels=10,
                stroked=True,
                get_line_color=[255, 255, 255, 220],
                get_line_width=1.0,
                line_width_min_pixels=0.8,
                pickable=True,
                auto_highlight=True,
                highlight_color=[0, 240, 255, 255],
            )
            deck_layers.append(core_veh_layer)

        # 2. Airport Layers (Vùng sân bay trọng điểm - Vòng radar to & nổi bật)
        if layer_airports:
            airport_df = pd.DataFrame([
                {"name": "JFK Intl Airport (JFK)", "lng": -73.7781, "lat": 40.6413, "count": jfk_cnt, "service_zone": "Queens / JFK"},
                {"name": "LaGuardia Airport (LGA)", "lng": -73.8740, "lat": 40.7769, "count": lga_cnt, "service_zone": "Queens / LGA"},
                {"name": "Newark Liberty Airport (EWR)", "lng": -74.1745, "lat": 40.6895, "count": ewr_cnt, "service_zone": "New Jersey / EWR"},
            ])
            airport_df["tooltip_html"] = [
                f'<div style="font-family:\'JetBrains Mono\',monospace;padding:8px 12px;font-size:11px;color:#F8FAFC;background:rgba(20,10,35,0.96);border-radius:6px;border:1.5px solid #A855F7;box-shadow:0 6px 20px rgba(0,0,0,0.8);min-width:210px;">'
                f'<b style="color:#C084FC;font-size:12px;">✈️ {r["name"]}</b>'
                f'<div style="margin-top:3px;">🚕 <b>Active Fleet:</b> <span style="color:#E9D5FF;font-weight:800;">{r["count"]} taxis</span></div>'
                f'<div style="color:#94A3B8;font-size:10px;">📍 <b>Location:</b> {r["service_zone"]}</div>'
                f'</div>'
                for r in airport_df.to_dict("records")
            ]

            # 2.1 Giant Outer Purple Radar Pulse Halo
            airport_outer_halo = pdk.Layer(
                "ScatterplotLayer",
                id="airport_outer_halo",
                data=airport_df,
                get_position=["lng", "lat"],
                get_fill_color=[168, 85, 247, 50],
                get_radius=1600,
                radius_min_pixels=32,
                radius_max_pixels=75,
                stroked=True,
                get_line_color=[192, 132, 252, 255],
                get_line_width=2.5,
                line_width_min_pixels=1.8,
                pickable=True,
                auto_highlight=True,
            )
            deck_layers.append(airport_outer_halo)

            # 2.2 Inner Core Airport Beacon Pin
            airport_core_pin = pdk.Layer(
                "ScatterplotLayer",
                id="airport_core_pin",
                data=airport_df,
                get_position=["lng", "lat"],
                get_fill_color=[147, 51, 234, 210],
                get_radius=500,
                radius_min_pixels=14,
                radius_max_pixels=28,
                stroked=True,
                get_line_color=[255, 255, 255, 255],
                get_line_width=2.0,
                line_width_min_pixels=1.2,
                pickable=False,
            )
            deck_layers.append(airport_core_pin)

        # 2.5 #1 Busiest Hotspot Radar Spotlight (Vùng đông khách nhất - Kích thước to, siêu nổi bật)
        if layer_busiest and busiest_zone and pd.notnull(busiest_zone.get("lat")) and pd.notnull(busiest_zone.get("lng")):
            b_df = pd.DataFrame([{
                "name": busiest_zone["zone_name"],
                "borough": busiest_zone.get("borough", "NYC"),
                "vehicle_count": busiest_zone.get("vehicle_count", 0),
                "congestion_level": busiest_zone.get("congestion_level", "NORMAL").replace("_", " "),
                "lat": float(busiest_zone["lat"]),
                "lng": float(busiest_zone["lng"])
            }])
            b_df["tooltip_html"] = [
                f'<div style="font-family:\'JetBrains Mono\',monospace;padding:8px 12px;font-size:11px;color:#F8FAFC;background:rgba(35,10,25,0.96);border-radius:6px;border:1.5px solid #F43F5E;box-shadow:0 6px 20px rgba(0,0,0,0.8);min-width:210px;">'
                f'<b style="color:#FB7185;font-size:12px;">🔥 #1 Hotspot: {r["name"]}</b> <span style="color:#94A3B8;">({r["borough"]})</span>'
                f'<div style="margin-top:3px;">🚕 <b>Active Fleet:</b> <span style="color:#FDA4AF;font-weight:800;">{r["vehicle_count"]} active taxis</span></div>'
                f'<div style="color:#F43F5E;font-size:10px;font-weight:700;">🚨 Status: {r["congestion_level"]}</div>'
                f'</div>'
                for r in b_df.to_dict("records")
            ]

            # 2.5.1 Giant Outer Radar Pulse Beacon (Đỏ Neon rực rỡ)
            busiest_outer_layer = pdk.Layer(
                "ScatterplotLayer",
                id="busiest_outer_halo",
                data=b_df,
                get_position=["lng", "lat"],
                get_fill_color=[244, 63, 94, 55],
                get_radius=2200,
                radius_min_pixels=40,
                radius_max_pixels=85,
                stroked=True,
                get_line_color=[255, 0, 80, 255],
                get_line_width=3.5,
                line_width_min_pixels=2.5,
                pickable=True,
                auto_highlight=True,
            )
            deck_layers.append(busiest_outer_layer)

            # 2.5.2 Concentric Amber Middle Pulse Ring
            busiest_mid_layer = pdk.Layer(
                "ScatterplotLayer",
                id="busiest_mid_ring",
                data=b_df,
                get_position=["lng", "lat"],
                get_fill_color=[245, 158, 11, 70],
                get_radius=1100,
                radius_min_pixels=22,
                radius_max_pixels=48,
                stroked=True,
                get_line_color=[251, 191, 36, 255],
                get_line_width=2.5,
                line_width_min_pixels=1.5,
                pickable=False,
            )
            deck_layers.append(busiest_mid_layer)

            # 2.5.3 Hotspot Core Pin (Tâm đỏ viền trắng)
            busiest_core_layer = pdk.Layer(
                "ScatterplotLayer",
                id="busiest_core_pin",
                data=b_df,
                get_position=["lng", "lat"],
                get_fill_color=[244, 63, 94, 240],
                get_radius=400,
                radius_min_pixels=10,
                radius_max_pixels=22,
                stroked=True,
                get_line_color=[255, 255, 255, 255],
                get_line_width=2.0,
                line_width_min_pixels=1.0,
                pickable=False,
            )
            deck_layers.append(busiest_core_layer)

        # 3. Dedicated Layers for Tracked Vehicle (Hiển thị rõ ràng xe và lộ trình đường phố thực tế)
        df_sel = pd.DataFrame()
        if selected_veh is not None:
            df_sel = pd.DataFrame([selected_veh])
            df_sel["lng"] = pd.to_numeric(df_sel.get("lng"), errors="coerce")
            df_sel["lat"] = pd.to_numeric(df_sel.get("lat"), errors="coerce")

            # 3.1 Đường lộ trình thực tế uốn lượn theo từng con phố (OSRM Road Network)
            s_lat = float(selected_veh.get("start_lat") or selected_veh.get("lat") or 40.75)
            s_lng = float(selected_veh.get("start_lng") or selected_veh.get("lng") or -73.98)
            t_lat = float(selected_veh.get("target_lat") or selected_veh.get("lat") or 40.75)
            t_lng = float(selected_veh.get("target_lng") or selected_veh.get("lng") or -73.98)
            prog = float(selected_veh.get("progress_ratio", 0.0) or 0.0)

            route_info = fetch_driving_route(s_lng, s_lat, t_lng, t_lat)
            route_coords = route_info.get("coordinates", [])
            opt_miles = route_info.get("optimal_distance_miles", 2.0)
            
            # Xác định vị trí xe bám sát trên tuyến đường thực tế
            if route_coords and len(route_coords) >= 1:
                split_idx = max(0, min(len(route_coords) - 1, int(prog * (len(route_coords) - 1))))
                snapped_cur = route_coords[split_idx]
            else:
                split_idx = 0
                snapped_cur = [s_lng, s_lat]

            # Cập nhật tọa độ hiển thị cho xe đang chọn để bám sát mặt đường
            df_sel["lng"] = snapped_cur[0]
            df_sel["lat"] = snapped_cur[1]
            df_sel["optimal_distance_val"] = opt_miles
            df_sel = format_fleet_df(df_sel)

            if not df_sel.empty:
                # 3.1.1 Đoạn đã đi: Pickup ➔ Vị trí hiện tại (Đường Cyan Neon uốn lượn theo phố)
                traveled_coords = route_coords[:split_idx + 1] if route_coords else []
                if len(traveled_coords) < 2:
                    traveled_coords = [route_coords[0], snapped_cur] if (route_coords and len(route_coords) >= 1) else [[s_lng, s_lat], [s_lng, s_lat]]

                sel_path_traveled = pdk.Layer(
                    "PathLayer",
                    data=[{"path": traveled_coords}],
                    get_path="path",
                    get_color=[0, 245, 255, 255],
                    get_width=4.5,
                    width_min_pixels=3.0,
                    rounded=True,
                    joint_rounded=True,
                    pickable=False,
                )
                deck_layers.append(sel_path_traveled)

                # 3.1.2 Đoạn sắp đi: Vị trí hiện tại ➔ Điểm trả (Đường Hồng/Đỏ Neon uốn lượn theo phố)
                remaining_coords = route_coords[split_idx:] if route_coords else []
                if len(remaining_coords) < 2:
                    remaining_coords = [snapped_cur, route_coords[-1]] if (route_coords and len(route_coords) >= 1) else [[t_lng, t_lat], [t_lng, t_lat]]

                sel_path_remaining = pdk.Layer(
                    "PathLayer",
                    data=[{"path": remaining_coords}],
                    get_path="path",
                    get_color=[244, 63, 94, 220],
                    get_width=3.5,
                    width_min_pixels=2.0,
                    rounded=True,
                    joint_rounded=True,
                    pickable=False,
                )
                deck_layers.append(sel_path_remaining)

                # 3.1.3 Nút Điểm đón (Xanh lá) & Điểm trả (Đỏ)
                sel_nodes = pdk.Layer(
                    "ScatterplotLayer",
                    data=pd.DataFrame([
                        {"lng": s_lng, "lat": s_lat, "color": [16, 185, 129, 255], "type": "Pickup"},
                        {"lng": t_lng, "lat": t_lat, "color": [244, 63, 94, 255], "type": "Dropoff"}
                    ]),
                    get_position=["lng", "lat"],
                    get_fill_color="color",
                    get_radius=60,
                    radius_min_pixels=5,
                    radius_max_pixels=10,
                    stroked=True,
                    get_line_color=[255, 255, 255, 255],
                    get_line_width=1.5,
                    line_width_min_pixels=1.0,
                    pickable=False,
                )
                deck_layers.append(sel_nodes)

                # 3.2 Vòng hào quang định vị nổi bật của xe được theo dõi
                sel_halo_layer = pdk.Layer(
                    "ScatterplotLayer",
                    data=df_sel,
                    get_position=["lng", "lat"],
                    get_fill_color=[0, 245, 255, 80],
                    get_radius=180,
                    radius_min_pixels=14,
                    radius_max_pixels=28,
                    stroked=True,
                    get_line_color=[0, 245, 255, 255],
                    get_line_width=1.5,
                    line_width_min_pixels=1.0,
                    pickable=False,
                )
                deck_layers.append(sel_halo_layer)

                # 3.3 Tâm xe được chọn (Trắng viền Cyan nổi bật)
                sel_focus_pin = pdk.Layer(
                    "ScatterplotLayer",
                    data=df_sel,
                    get_position=["lng", "lat"],
                    get_fill_color=[255, 255, 255, 255],
                    get_radius=80,
                    radius_min_pixels=7,
                    radius_max_pixels=15,
                    stroked=True,
                    get_line_color=[0, 200, 255, 255],
                    get_line_width=2.5,
                    line_width_min_pixels=1.5,
                    pickable=True,
                    auto_highlight=True,
                )
                deck_layers.append(sel_focus_pin)

        # Dynamic View State: If vehicle is selected, zoom directly onto the moving driver
        if selected_veh is not None and not df_sel.empty:
            view_state = pdk.ViewState(
                latitude=float(df_sel.iloc[0]["lat"]),
                longitude=float(df_sel.iloc[0]["lng"]),
                zoom=15.2,
                pitch=45,
                bearing=-10,
                transition_duration=200,
            )
        else:
            view_state = pdk.ViewState(
                latitude=cur_preset["lat"],
                longitude=cur_preset["lng"],
                zoom=cur_preset["zoom"],
                pitch=cur_preset["pitch"],
                bearing=-8,
            )

        deck = pdk.Deck(
            layers=deck_layers,
            initial_view_state=view_state,
            map_style="mapbox://styles/mapbox/dark-v11",
            tooltip={
                "html": "{tooltip_html}",
                "style": {
                    "color": "white",
                    "pointer-events": "none",
                    "user-select": "none",
                    "z-index": "99999",
                }
            }
        )

        st.pydeck_chart(deck, use_container_width=True)

        # In-Map Sleek Visual Legend (English)
        legend_html = """<div style="background:rgba(15,23,42,0.92); backdrop-filter:blur(8px); border:1px solid rgba(56,189,248,0.22); border-radius:8px; padding:0 14px; height:38px; margin-top:6px; display:flex; flex-wrap:nowrap; justify-content:space-between; align-items:center; gap:8px; font-size:0.73rem; color:#CBD5E1; box-sizing:border-box;">
<span style="font-weight:800; color:#38BDF8; letter-spacing:0.04em;">🗺️ MAP LEGEND:</span>
<span><b style="color:#FACC15;">🟡</b> Yellow Cab</span>
<span><b style="color:#22C55E;">🟢</b> Green Cab</span>
<span><b style="color:#A855F7;">🟣</b> FHVHV (Uber/Lyft)</span>
<span><b style="color:#00F0FF;">●</b><b style="color:#10B981;">●</b><b style="color:#FACC15;">●</b><b style="color:#F43F5E;">●</b> Demand Heat</span>
<span><b style="color:#F43F5E;">🚨 Red</b>: #1 Hotspot</span>
<span><b style="color:#C084FC;">✈️ Purple</b>: Airports</span>
<span><b style="color:#00F5FF;">━━</b> Traveled</span>
<span><b style="color:#F43F5E;">━━</b> Remaining</span>
</div>"""
        st.markdown(legend_html, unsafe_allow_html=True)

    # ── Right Column: Interactive Fleet & Corridor Dispatch Table ──
    with right_col:
        st.markdown("#### 🧭 Fleet & Route Corridor Dispatch")

        # Real-time Search Box for Fleet Dispatch
        search_query = st.text_input(
            "Search Trip ID, Zone, Borough",
            value="",
            placeholder="🔍 Search Trip ID, Zone, Borough...",
            key="fleet_search_input",
            label_visibility="collapsed"
        ).strip().lower()

        if not df_v_fmt.empty:
            df_filtered = df_v_fmt

            # Real-time search filtering across Trip ID, Pickup/Dropoff Zones, and Boroughs
            if search_query:
                mask = (
                    df_filtered["trip_id"].astype(str).str.lower().str.contains(search_query, na=False) |
                    df_filtered["zone_name"].astype(str).str.lower().str.contains(search_query, na=False) |
                    df_filtered["dropoff_zone_name"].astype(str).str.lower().str.contains(search_query, na=False) |
                    df_filtered["borough"].astype(str).str.lower().str.contains(search_query, na=False) |
                    df_filtered["dropoff_borough"].astype(str).str.lower().str.contains(search_query, na=False)
                )
                df_filtered = df_filtered[mask]
                st.caption(f"🔎 Found **{len(df_filtered)}** matching vehicles")

            if df_filtered.empty and search_query:
                st.info(f"No active vehicles match '{search_query}'.")

            # Prioritize selected vehicle to top of dispatch list if present
            if st.session_state.selected_trip_id and not df_filtered.empty:
                is_sel = (df_filtered["trip_id"].astype(str) == str(st.session_state.selected_trip_id))
                if is_sel.any():
                    df_filtered = pd.concat([df_filtered[is_sel], df_filtered[~is_sel]])

            # ── PAGINATION & SCROLL CONTAINER ──
            PAGE_SIZE = 6
            total_items = len(df_filtered)
            total_pages = max(1, (total_items + PAGE_SIZE - 1) // PAGE_SIZE)
            
            if st.session_state.fleet_page > total_pages:
                st.session_state.fleet_page = total_pages
            if st.session_state.fleet_page < 1:
                st.session_state.fleet_page = 1
                
            cur_page = st.session_state.fleet_page
            start_idx = (cur_page - 1) * PAGE_SIZE
            end_idx = min(start_idx + PAGE_SIZE, total_items)
            df_page = df_filtered.iloc[start_idx:end_idx]

            # Scrollable container for vehicle cards to prevent layout overflow
            with st.container(height=615, border=False):
                for r in df_page.to_dict("records"):
                    tid = str(r["trip_id"])
                    prog = float(r.get("progress_ratio", 0.0) or 0.0)
                    fare_val = float(r.get("fare_amount", 0.0) or 0.0)
                    is_this_selected = (st.session_state.selected_trip_id == tid)
                    eff_col = r.get("efficiency_color", "#10B981")
                    eff_bdg = r.get("efficiency_badge", "🟢 OPTIMAL")
                    eff_val = r.get("efficiency_pct", 95)
                    c_icon = str(r.get("taxi_type_icon", "🚖"))
                    c_name = str(r.get("taxi_type_name", "Yellow Cab"))
                    c_hex = str(r.get("taxi_type_color_hex", "#FACC15"))
                    borough_name = str(r.get("borough", "Manhattan"))
                    
                    card_class = "fleet-card-active" if is_this_selected else ""
                    
                    st.markdown(
                        f"""
                        <div class="{card_class}" style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 10px 12px; margin-bottom: 6px;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                                <span style="font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; font-weight: 700; color: {'#38BDF8' if not is_this_selected else '#00F5FF'}; display: flex; align-items: center; gap: 4px;">
                                    <span>{c_icon}</span>
                                    {'🎯 ' if is_this_selected else ''}{tid}
                                </span>
                                <div style="display: flex; gap: 4px; align-items: center;">
                                    <span style="font-size: 0.65rem; font-weight: 700; color: {c_hex}; background: rgba(255,255,255,0.06); border: 1px solid {c_hex}55; padding: 1px 5px; border-radius: 4px;">{c_name}</span>
                                    <span style="font-size: 0.72rem; font-weight: 700; color: #38BDF8; background: rgba(56,189,248,0.15); border: 1px solid rgba(56,189,248,0.3); padding: 2px 6px; border-radius: 4px;">${fare_val:.2f}</span>
                                </div>
                            </div>
                            <div style="font-size: 0.82rem; font-weight: 600; color: #F1F5F9; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                                {r.get('zone_name', 'N/A')} ➔ {r.get('dropoff_zone_name', 'Destination')}
                            </div>
                            <div style="font-size: 0.72rem; color: #94A3B8; margin-top: 3px; display: flex; align-items: center; gap: 4px;">
                                <span>🏙️ Borough:</span> <b style="color: #E2E8F0;">{borough_name}</b>
                            </div>
                            <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: #94A3B8; margin-top: 4px;">
                                <span>⚡ {float(r.get('speed_mph', 15.0)):.0f} mph</span>
                                <span>💵 ${fare_val:.2f}</span>
                                <span>Progress: <b>{int(prog * 100)}%</b></span>
                            </div>
                            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.72rem; margin-top: 5px; padding-top: 4px; border-top: 1px solid rgba(255,255,255,0.06);">
                                <span style="color: {eff_col}; font-weight: 700;">{eff_bdg}</span>
                                <span style="color: #94A3B8;">Eff: <b style="color:#F1F5F9;">{eff_val}%</b> (Opt: {r.get('optimal_distance_fmt', '2.0')} mi)</span>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    st.progress(min(1.0, max(0.05, prog)))

                    # Click target button to track / focus on this driver (Full width)
                    if is_this_selected:
                        if st.button("📍 Tracking Active (Stop)", key=f"track_btn_{tid}", type="primary", use_container_width=True):
                            st.session_state.selected_trip_id = None
                            st.session_state.tracked_vehicle_cache.clear()
                            st.query_params.clear()
                            st.rerun()
                    else:
                        if st.button("🎯 Track Vehicle", key=f"track_btn_{tid}", use_container_width=True):
                            st.session_state.selected_trip_id = tid
                            st.query_params.clear()
                            st.rerun()

                    st.markdown("<div style='margin-bottom: 8px;'></div>", unsafe_allow_html=True)

            # ── COMPACT BOTTOM PAGINATION (ALIGNED WITH MAP LEGEND) ──
            pg_col1, pg_col2, pg_col3 = st.columns([1.1, 1.4, 1.1])
            with pg_col1:
                if st.button("◀ Prev", disabled=(cur_page <= 1), key="btn_prev_fleet_page_bottom", use_container_width=True):
                    st.session_state.fleet_page -= 1
                    st.rerun()
            with pg_col2:
                st.markdown(
                    f"<div style='text-align: center; font-size: 0.78rem; color: #94A3B8; font-weight: 700; height: 38px; display: flex; align-items: center; justify-content: center;'>Page <b>&nbsp;{cur_page}&nbsp;</b> / <b>&nbsp;{total_pages}&nbsp;</b></div>",
                    unsafe_allow_html=True,
                )
            with pg_col3:
                if st.button("Next ▶", disabled=(cur_page >= total_pages), key="btn_next_fleet_page_bottom", use_container_width=True):
                    st.session_state.fleet_page += 1
                    st.rerun()
        else:
            st.info("Awaiting stream corridor telemetry from Kafka/Redis...")

# ── TAB 2: Live Stream Telemetry & Trends ──────────────────────────────────
with tab2:
    # Operations Status Bar & Executive KPI Grid
    st.markdown(ops_bar_html, unsafe_allow_html=True)
    st.markdown(kpi_html, unsafe_allow_html=True)

    # Fleet Telemetry Performance Indicator Cards
    df_v_stream_all = pd.DataFrame(active_vehicles) if active_vehicles else pd.DataFrame(columns=["speed_mph", "progress_ratio", "fare_amount", "trip_id", "zone_name", "dropoff_zone_name", "borough", "dataset_source"])
    if not df_v_stream_all.empty:
        df_v_stream_all["dataset_source"] = get_column_series(df_v_stream_all, "dataset_source", "YELLOW").astype(str).str.upper()
        if allowed_sources:
            df_v_stream_all = df_v_stream_all[df_v_stream_all["dataset_source"].isin(allowed_sources)]
        else:
            df_v_stream_all = df_v_stream_all.iloc[0:0]

    if selected_borough != "All NYC" and not df_v_stream_all.empty:
        df_v_stream = df_v_stream_all[df_v_stream_all["borough"] == selected_borough].copy()
    else:
        df_v_stream = df_v_stream_all.copy()
    st.markdown("### 📈 High-Frequency Stream Telemetry & Real-Time Waveforms")

    hist = st.session_state.history
    has_hist = len(hist["timestamps"]) > 1

    # ── ROW 1: Real-Time Ingestion Velocity & Top Active Pickup Zones Concentration ──
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        if has_hist:
            fig_tp = go.Figure()
            # Ingestion Throughput Glowing Gradient Spline
            fig_tp.add_trace(go.Scatter(
                x=hist["timestamps"],
                y=hist["throughput_rate"],
                mode="lines+markers",
                name="Instantaneous (Evt/s)",
                line=dict(color="#FBBF24", width=3, shape="spline"),
                fill="tozeroy",
                fillcolor="rgba(251, 191, 36, 0.18)",
                marker=dict(size=5, color="#FBBF24")
            ))
            fig_tp.update_layout(
                title="<b>⚡ Kafka Stream Ingestion Velocity (Events / Sec Pulse)</b>",
                template="plotly_dark",
                height=320,
                margin=dict(l=20, r=20, t=40, b=20),
                yaxis=dict(title="Events / Second", gridcolor="rgba(255,255,255,0.06)", zeroline=False),
                xaxis=dict(gridcolor="rgba(255,255,255,0.06)", showgrid=True, nticks=6, tickangle=0),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_tp, use_container_width=True, config={'displayModeBar': False})
        else:
            st.info("Accumulating live Kafka stream ingestion telemetry...")

    with chart_col2:
        # Top Active Pickup Zones Concentration (Horizontal Bar Chart)
        if not df_v_stream.empty:
            df_bar = df_v_stream.copy()
            df_bar["display_zone"] = get_column_series(df_bar, "zone_name", "").astype(str).str.strip()
            df_bar["display_borough"] = get_column_series(df_bar, "borough", "").astype(str).str.strip()

            df_bar["zone_label"] = df_bar.apply(
                lambda r: r["display_zone"] if r["display_zone"] and r["display_zone"] not in ["NYC", "None", "nan"]
                else (r["display_borough"] if r["display_borough"] and r["display_borough"] not in ["None", "nan"] else "Manhattan"),
                axis=1
            )
            df_bar["fare_amount"] = get_numeric_series(df_bar, "fare_amount", 0.0)
            df_bar["speed_mph"] = get_numeric_series(df_bar, "speed_mph", 15.0)

            zone_agg = df_bar.groupby("zone_label").agg(
                taxi_count=("trip_id", "count"),
                avg_speed=("speed_mph", "mean"),
                avg_fare=("fare_amount", "mean")
            ).reset_index()

            # Get Top 8 zones sorted ascending for horizontal display
            zone_agg = zone_agg.sort_values(by="taxi_count", ascending=True).tail(8)

            fig_zone_bar = go.Figure()
            fig_zone_bar.add_trace(go.Bar(
                x=zone_agg["taxi_count"],
                y=zone_agg["zone_label"],
                orientation="h",
                marker=dict(
                    color=zone_agg["taxi_count"],
                    colorscale=[[0, "#38BDF8"], [0.5, "#818CF8"], [1, "#F43F5E"]],
                    line=dict(color="rgba(255,255,255,0.25)", width=1)
                ),
                text=zone_agg["taxi_count"].apply(lambda v: f" {v} taxis"),
                textposition="outside",
                textfont=dict(color="#E2E8F0", size=11, family="JetBrains Mono, sans-serif"),
                hovertemplate="<b>%{y}</b><br>Active Taxis: %{x}<br>Avg Fare: $%{customdata[0]:.2f}<br>Avg Speed: %{customdata[1]:.1f} mph<extra></extra>",
                customdata=zone_agg[["avg_fare", "avg_speed"]].values
            ))

            fig_zone_bar.update_layout(
                title=f"<b>📍 Active Fleet Concentration ({selected_borough})</b>",
                template="plotly_dark",
                height=320,
                margin=dict(l=20, r=35, t=40, b=20),
                xaxis=dict(
                    title="Active Vehicles",
                    gridcolor="rgba(255,255,255,0.06)",
                    zeroline=False
                ),
                yaxis=dict(
                    title="",
                    gridcolor="rgba(255,255,255,0.06)",
                    automargin=True
                ),
                showlegend=False
            )
            st.plotly_chart(fig_zone_bar, use_container_width=True, config={'displayModeBar': False})
        else:
            st.info("Awaiting active vehicle telemetry for zone distribution...")

    # ── ROW 3: Regional Borough Distribution & Mobility Analytics ──
    chart_col5, chart_col6 = st.columns(2)

    with chart_col5:
        # Donut Chart: Borough Market Share of Active Trips
        if not df_v_stream_all.empty:
            b_series = get_column_series(df_v_stream_all, "borough", "Manhattan")
            b_counts = b_series.value_counts().reset_index()
            b_counts.columns = ["borough", "count"]
            borough_color_map = {
                "Manhattan": "#38BDF8",
                "Brooklyn": "#818CF8",
                "Queens": "#34D399",
                "Bronx": "#FBBF24",
                "Staten Island": "#F43F5E",
                "EWR": "#EC4899",
            }
            colors = [borough_color_map.get(b, "#94A3B8") for b in b_counts["borough"]]

            fig_donut = go.Figure(data=[go.Pie(
                labels=b_counts["borough"],
                values=b_counts["count"],
                hole=0.55,
                marker=dict(colors=colors, line=dict(color="#0F172A", width=2)),
                textinfo="label+percent",
                textposition="inside",
                insidetextorientation="horizontal",
                hovertemplate="<b>%{label}</b><br>Active Taxis: <b>%{value:,}</b> (%{percent})<extra></extra>",
                textfont=dict(size=11, family="JetBrains Mono, sans-serif", color="#FFFFFF")
            )])
            fig_donut.update_layout(
                title="<b>🏙️ Borough Fleet Market Share Distribution</b>",
                template="plotly_dark",
                height=320,
                margin=dict(l=20, r=20, t=40, b=30),
                legend=dict(orientation="h", yanchor="top", y=-0.08, xanchor="center", x=0.5, font=dict(size=11, family="Plus Jakarta Sans, sans-serif")),
                annotations=[dict(
                    text=f"<b>{len(df_v_stream_all):,}</b><br><span style='font-size:10px;color:#94A3B8'>TAXIS</span>",
                    x=0.5, y=0.5,
                    font=dict(size=16, family="JetBrains Mono, sans-serif", color="#F8FAFC"),
                    showarrow=False
                )]
            )
            st.plotly_chart(fig_donut, use_container_width=True, config={'displayModeBar': False})
        else:
            st.info("Accumulating borough distribution data...")

    with chart_col6:
        # In-Flight Fare Distribution Histogram
        if not df_v_stream.empty and "fare_amount" in df_v_stream.columns:
            df_hist = df_v_stream.copy()
            df_hist["fare_amount"] = get_numeric_series(df_hist, "fare_amount", 0.0)
            df_hist["dataset_source"] = get_column_series(df_hist, "dataset_source", "YELLOW").astype(str).str.upper()
            
            type_label_map = {"YELLOW": "🚖 Yellow Cab", "GREEN": "🚕 Green Cab", "FHVHV": "📱 FHVHV"}
            type_colors = {"YELLOW": "#FACC15", "GREEN": "#22C55E", "FHVHV": "#A855F7"}
            
            fig_fare_dist = go.Figure()
            for ds in ["YELLOW", "FHVHV", "GREEN"]:
                ds_data = df_hist[df_hist["dataset_source"] == ds]
                if not ds_data.empty:
                    fig_fare_dist.add_trace(go.Histogram(
                        x=ds_data["fare_amount"],
                        name=type_label_map.get(ds, ds),
                        marker=dict(
                            color=type_colors.get(ds, "#38BDF8"),
                            line=dict(color="#0F172A", width=1)
                        ),
                        opacity=0.85,
                        xbins=dict(size=5.0),
                        hovertemplate="<b>%{data.name}</b><br>Fare: $%{x:.1f}<br>Trips: <b>%{y}</b><extra></extra>"
                    ))

            avg_fare = df_hist["fare_amount"].mean()

            fig_fare_dist.update_layout(
                title=f"<b>📊 In-Flight Fare Distribution ({selected_borough})</b>",
                template="plotly_dark",
                height=320,
                barmode="stack",
                margin=dict(l=20, r=20, t=40, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10, family="Plus Jakarta Sans, sans-serif")),
                xaxis=dict(
                    title="In-Flight Fare Amount ($)",
                    tickprefix="$",
                    gridcolor="rgba(255,255,255,0.06)",
                    zeroline=False
                ),
                yaxis=dict(
                    title="Active Trip Count",
                    gridcolor="rgba(255,255,255,0.06)",
                    zeroline=False
                ),
            )
            if pd.notnull(avg_fare) and avg_fare > 0:
                fig_fare_dist.add_vline(
                    x=avg_fare,
                    line_dash="dash",
                    line_color="#38BDF8",
                    annotation_text=f"Avg: ${avg_fare:.1f}",
                    annotation_position="top right",
                    annotation_font=dict(size=10, color="#38BDF8", family="JetBrains Mono, sans-serif")
                )
            st.plotly_chart(fig_fare_dist, use_container_width=True, config={'displayModeBar': False})
        else:
            st.info(f"Accumulating live in-flight fare distribution for {selected_borough}...")

    # ── ROW 4: Live Micro-Batch Stream Ingestion Feed ──
    st.markdown("---")
    st.markdown(
        f"""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
            <span style="font-size: 1.05rem; font-weight: 800; color: #F8FAFC;">📡 Live Micro-Batch Ingestion Stream Feed ({selected_borough})</span>
            <span style="font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; color: #34D399; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.35); padding: 3px 10px; border-radius: 20px;">
                ● STREAM ACTIVE &bull; {len(df_v_stream)} PINGS IN SLIDING WINDOW
            </span>
        </div>
        """,
        unsafe_allow_html=True
    )

    if not df_v_stream.empty:
        df_feed = df_v_stream.copy()
        df_feed["dataset_source"] = get_column_series(df_feed, "dataset_source", "YELLOW").astype(str).str.upper()
        
        type_icon_map = {"YELLOW": "🚖 Yellow Cab", "GREEN": "🚕 Green Cab", "FHVHV": "📱 FHVHV"}
        df_feed["taxi_type"] = [type_icon_map.get(ds, "🚖 Yellow Cab") for ds in df_feed["dataset_source"]]
        df_feed["speed_mph"] = get_numeric_series(df_feed, "speed_mph", 15.0)
        df_feed["fare_amount"] = get_numeric_series(df_feed, "fare_amount", 0.0)
        df_feed["progress_ratio"] = get_numeric_series(df_feed, "progress_ratio", 0.0)
        
        def assign_status(s, p):
            if p >= 0.85: return "🏁 ARRIVING_SOON"
            if s >= 24.0: return "🏎️ EXPRESS_SPEED"
            if s < 6.0: return "⚠️ HEAVY_TRAFFIC"
            return "🚕 CRUISING"

        speeds = df_feed["speed_mph"].values
        progs = df_feed["progress_ratio"].values
        df_feed["live_status"] = [assign_status(s, p) for s, p in zip(speeds, progs)]
        df_feed["corridor"] = [f"{z} ➔ {dz}" for z, dz in zip(df_feed["zone_name"].fillna("NYC"), df_feed["dropoff_zone_name"].fillna("Destination"))]

        # Sort so high-fare / high-activity trips are highlighted at top
        df_feed = df_feed.sort_values(by=["fare_amount", "speed_mph"], ascending=[False, False]).head(20)

        st.dataframe(
            df_feed[["trip_id", "taxi_type", "corridor", "borough", "fare_amount", "progress_ratio", "live_status"]],
            column_config={
                "trip_id": st.column_config.TextColumn("Trip ID"),
                "taxi_type": st.column_config.TextColumn("🚖 Fleet Type"),
                "corridor": st.column_config.TextColumn("📍 Route Corridor (Pickup ➔ Dropoff)"),
                "borough": st.column_config.TextColumn("Borough"),
                "fare_amount": st.column_config.NumberColumn("💵 In-Flight Fare", format="$%.2f"),
                "progress_ratio": st.column_config.ProgressColumn("🎯 Trip Progress", format="%.0f%%", min_value=0.0, max_value=1.0),
                "live_status": st.column_config.TextColumn("📡 Dynamic Status"),
            },
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info(f"Awaiting telemetry pulses for {selected_borough} from stream ingestion pipeline...")



# ── TAB 3: ⚔️ Fleet Power Map ─────────────────────────────────────────────
with tab3:
    # ── Power Map CSS ──
    st.markdown("""
    <style>
    .territory-bar-wrap {
        background: rgba(15,23,42,0.85);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px;
        padding: 14px 20px;
        margin-bottom: 16px;
    }
    .pm-card {
        background: rgba(15,23,42,0.80);
        border: 1px solid rgba(255,255,255,0.07);
        border-left: 4px solid #38BDF8;
        border-radius: 8px;
        padding: 10px 14px;
        margin-bottom: 8px;
        transition: transform 0.2s;
    }
    .pm-card:hover { transform: translateX(4px); }
    .pm-card.contested { border-left-color: #EAB308; }
    .pm-card.yellow-dom { border-left-color: #FACC15; }
    .pm-card.green-dom { border-left-color: #22C55E; }
    .pm-card.fhvhv-dom { border-left-color: #A855F7; }

    .pm-feed-container {
        max-height: 650px;
        overflow-y: auto;
        overflow-x: hidden;
        padding-right: 6px;
        scrollbar-width: thin;
        scrollbar-color: rgba(56, 189, 248, 0.4) rgba(15, 23, 42, 0.6);
    }
    .pm-feed-container::-webkit-scrollbar { width: 6px; }
    .pm-feed-container::-webkit-scrollbar-track { background: rgba(15, 23, 42, 0.6); border-radius: 4px; }
    .pm-feed-container::-webkit-scrollbar-thumb { background: rgba(56, 189, 248, 0.4); border-radius: 4px; }
    .pm-feed-container::-webkit-scrollbar-thumb:hover { background: rgba(56, 189, 248, 0.8); }

    .pm-pill {
        display: inline-flex; align-items: center; gap: 6px;
        background: rgba(15,23,42,0.75);
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 20px;
        padding: 5px 14px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.78rem;
        color: #E2E8F0;
        font-weight: 600;
    }
    .pm-dot { width:10px; height:10px; border-radius:50%; display:inline-block; }
    .pm-legend-card {
        background: rgba(15,23,42,0.80);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 10px;
        padding: 8px 16px;
        margin-bottom: 12px;
    }
    </style>
    """, unsafe_allow_html=True)

    # ── Data prep ──
    pm_all_zones_raw = density.get("all_zones", [])
    invasion_zones_raw = power_map_data.get("invasion_zones", [])
    territory_counts = power_map_data.get("territory_counts",
                           density.get("territory_counts", {}))

    if selected_borough != "All NYC":
        pm_all_zones = [z for z in pm_all_zones_raw if z.get("borough") == selected_borough]
        active_zones_list = [z for z in invasion_zones_raw if z.get("borough") == selected_borough]
        y_zones = sum(1 for z in pm_all_zones if z.get("dominant_fleet") == "YELLOW")
        g_zones = sum(1 for z in pm_all_zones if z.get("dominant_fleet") == "GREEN")
        h_zones = sum(1 for z in pm_all_zones if z.get("dominant_fleet") == "FHVHV")
        n_zones = sum(1 for z in pm_all_zones if not z.get("dominant_fleet") or z.get("dominant_fleet") == "NONE")
        c_zones = sum(1 for z in pm_all_zones if z.get("battle_status") == "CONTESTED")
    else:
        pm_all_zones = pm_all_zones_raw
        active_zones_list = invasion_zones_raw
        y_zones = territory_counts.get("YELLOW", 0)
        g_zones = territory_counts.get("GREEN",  0)
        h_zones = territory_counts.get("FHVHV",  0)
        n_zones = territory_counts.get("NONE",   0)
        c_zones = sum(1 for z in pm_all_zones if z.get("battle_status") == "CONTESTED")

    total_dom_zones = max(1, y_zones + g_zones + h_zones + n_zones)
    y_pct = round(y_zones / total_dom_zones * 100, 1)
    g_pct = round(g_zones / total_dom_zones * 100, 1)
    h_pct = round(h_zones / total_dom_zones * 100, 1)

    # ── Territory Header ──
    st.markdown(
        f"""
        <div class="territory-bar-wrap">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
            <span style="font-size:1.05rem; font-weight:800; color:#F8FAFC;">⚔️ NYC Zone Territory Control ({selected_borough})</span>
            <div style="display:flex; gap:8px; flex-wrap:wrap;">
              <span class="pm-pill"><span class="pm-dot" style="background:#FACC15;"></span>🚖 Yellow <b>{y_zones}</b> zones ({y_pct}%)</span>
              <span class="pm-pill"><span class="pm-dot" style="background:#22C55E;"></span>🚕 Green <b>{g_zones}</b> zones ({g_pct}%)</span>
              <span class="pm-pill"><span class="pm-dot" style="background:#A855F7;"></span>📱 FHVHV <b>{h_zones}</b> zones ({h_pct}%)</span>
              <span class="pm-pill" style="border-color:rgba(234,179,8,0.4);"><span class="pm-dot" style="background:#EAB308;"></span>⚡ Contested: <b>{c_zones}</b></span>
            </div>
          </div>
          <!-- 3-fleet territory bar -->
          <div style="width:100%; height:10px; border-radius:5px; overflow:hidden; background:rgba(255,255,255,0.06); display:flex;">
            <div style="width:{y_pct}%; background:linear-gradient(90deg,#FACC15,#EAB308); height:100%;"></div>
            <div style="width:{g_pct}%; background:linear-gradient(90deg,#22C55E,#16A34A); height:100%;"></div>
            <div style="width:{h_pct}%; background:linear-gradient(90deg,#A855F7,#7C3AED); height:100%;"></div>
          </div>
          <div style="display:flex; justify-content:space-between; font-size:0.72rem; color:#64748B; margin-top:5px; font-family:'JetBrains Mono',monospace;">
            <span>Territory dominance determined by majority active fleet · Real-time stream updates</span>
            <span>{len(pm_all_zones)} Zones tracked in {selected_borough}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Power Map Simple Legend ──
    st.markdown(
        """
        <div class="pm-legend-card">
          <div style="display:flex; gap:10px; flex-wrap:wrap; align-items:center; justify-content:space-between;">
            <div style="display:flex; gap:8px; flex-wrap:wrap; align-items:center;">
              <span class="pm-pill"><span class="pm-dot" style="background:#FACC15;"></span> Yellow Cab</span>
              <span class="pm-pill"><span class="pm-dot" style="background:#22C55E;"></span> Green Taxi</span>
              <span class="pm-pill"><span class="pm-dot" style="background:#A855F7;"></span> FHVHV (Uber/Lyft)</span>
              <span class="pm-pill" style="border-color:rgba(234,179,8,0.4);"><span class="pm-dot" style="background:#EAB308;"></span> ⚡ Contested</span>
            </div>
            <div style="font-size:0.74rem; color:#94A3B8; font-family:'JetBrains Mono',monospace;">
              <span>● <b>Circle Size:</b> Vehicle count</span>
              <span style="margin: 0 6px; color:#475569;">•</span>
              <span>⬡ <b>Overlap:</b> Shared busy border</span>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Build PyDeck Power Map Data ──
    pm_records = []
    _FLEET_COLOR_MAP = {
        "YELLOW": [250, 204, 21],
        "GREEN":  [34,  197, 94],
        "FHVHV":  [168, 85,  247],
    }
    _FLEET_NAME_MAP = {
        "YELLOW": "Yellow Cab",
        "GREEN":  "Green Boro Taxi",
        "FHVHV":  "FHVHV (Uber/Lyft)",
        "NONE":   "No Vehicles",
    }

    for z in pm_all_zones:
        if not z.get("lat") or not z.get("lng"):
            continue
        dom_fleet = z.get("dominant_fleet", "NONE")
        dom_ratio = float(z.get("dominance_ratio", 0.0))
        battle    = z.get("battle_status", "EMPTY")
        v_count   = int(z.get("vehicle_count", 0))
        fb        = z.get("fleet_breakdown", {})
        fr        = z.get("fleet_ratios", {})

        # Color logic
        if v_count == 0:
            fill_color = [71, 85, 105, 40]
            line_color = [255, 255, 255, 20]
            line_width = 1.0
            radius = 260
        elif battle == "CONTESTED":
            fill_color = [234, 179, 8, 210]
            line_color = [251, 191, 36, 255]
            line_width = 2.5
            radius = max(320, min(2200, v_count * 150))
        elif dom_fleet in _FLEET_COLOR_MAP:
            rgb = _FLEET_COLOR_MAP[dom_fleet]
            fill_color = rgb + [200]
            line_color = [255, 255, 255, 120]
            line_width = 1.5
            radius = max(300, min(2200, v_count * 140))
        else:
            fill_color = [100, 116, 139, 120]
            line_color = [255, 255, 255, 40]
            line_width = 1.0
            radius = 300

        battle_label = {
            "DOMINATED": "👑 DOMINATED",
            "CONTESTED": "⚡ CONTESTED",
            "BALANCED":  "⚖️ BALANCED",
            "EMPTY":     "○ EMPTY",
        }.get(battle, battle)

        y_num = fb.get("YELLOW", 0)
        g_num = fb.get("GREEN", 0)
        h_num = fb.get("FHVHV", 0)

        tooltip_html = (
            f'<div style="font-family:\'JetBrains Mono\',monospace; padding:12px 16px; '
            f'font-size:11px; color:#F8FAFC; background:rgba(11,17,32,0.97); '
            f'border-radius:10px; border:1.5px solid {"#EAB308" if battle=="CONTESTED" else "#334155"}; '
            f'box-shadow:0 8px 28px rgba(0,0,0,0.85); min-width:240px;">'
            f'<div style="font-size:13px; font-weight:800; color:#F8FAFC; '
            f'border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:5px; margin-bottom:7px;">'
            f'📍 {z.get("zone_name","Zone")} <span style="color:#64748B; font-size:10px;">({z.get("borough","NYC")})</span></div>'
            f'<div style="margin-bottom:4px;">🚕 <b>Total Vehicles:</b> <span style="color:#38BDF8; font-weight:800;">{v_count}</span></div>'
            f'<div style="margin-bottom:4px;">👑 <b>Dominant Fleet:</b> <span style="font-weight:800; color:{"#FACC15" if dom_fleet=="YELLOW" else ("#22C55E" if dom_fleet=="GREEN" else ("#A855F7" if dom_fleet=="FHVHV" else "#94A3B8"))};">'
            f'{_FLEET_NAME_MAP.get(dom_fleet, "N/A")} ({round(dom_ratio*100)}%)</span></div>'
            f'<div style="margin-bottom:4px; font-size:10px; color:#94A3B8;">📊 🚖 Yellow: {y_num} · 🚕 Green: {g_num} · 📱 FHV: {h_num}</div>'
            f'<div style="font-size:10px;">⚡ <b>Status:</b> {battle_label}</div>'
            f'</div>'
        )

        pm_records.append({
            "lat": float(z["lat"]),
            "lng": float(z["lng"]),
            "zone_name": z.get("zone_name", ""),
            "borough": z.get("borough", ""),
            "vehicle_count": v_count,
            "dominant_fleet": dom_fleet,
            "dominance_ratio": dom_ratio,
            "battle_status": battle,
            "fill_color": fill_color,
            "line_color": line_color,
            "line_width": line_width,
            "radius": radius,
            "tooltip_html": tooltip_html,
        })

    pm_map_col, pm_right_col = st.columns([3.5, 1.5])

    with pm_map_col:
        if pm_records:
            pm_df = pd.DataFrame(pm_records)

            # ── Single Clean ScatterplotLayer ──
            zone_dom_layer = pdk.Layer(
                "ScatterplotLayer",
                id="zone_dominance_layer",
                data=pm_df,
                get_position=["lng", "lat"],
                get_fill_color="fill_color",
                get_radius="radius",
                radius_min_pixels=6,
                radius_max_pixels=50,
                stroked=True,
                get_line_color="line_color",
                get_line_width="line_width",
                line_width_min_pixels=1,
                pickable=True,
                auto_highlight=True,
                highlight_color=[0, 240, 255, 70],
            )

            pm_lat = 40.7420
            pm_lng = -73.9700
            pm_zoom = 11.5
            if selected_borough in borough_preset_coords:
                pm_lat = borough_preset_coords[selected_borough]["lat"]
                pm_lng = borough_preset_coords[selected_borough]["lng"]
                pm_zoom = max(10.5, borough_preset_coords[selected_borough]["zoom"] - 0.8)

            pm_deck = pdk.Deck(
                layers=[zone_dom_layer],
                initial_view_state=pdk.ViewState(
                    latitude=pm_lat,
                    longitude=pm_lng,
                    zoom=pm_zoom,
                    pitch=0,
                    bearing=0,
                ),
                tooltip={"html": "{tooltip_html}", "style": {"background": "none", "border": "none", "padding": "0"}},
                map_style="mapbox://styles/mapbox/dark-v11",
            )
            st.pydeck_chart(pm_deck, use_container_width=True)
        else:
            st.info("⏳ Awaiting fleet distribution metrics from stream processor...")

    with pm_right_col:
        # ── Active / Contested Zones Feed ──
        st.markdown(
            f"""
            <div style="font-size:0.95rem; font-weight:800; color:#F8FAFC; margin-bottom:10px; display:flex; justify-content:space-between; align-items:center;">
              <span>⚔️ Active & Contested Zones</span>
              <span style="font-family:'JetBrains Mono',monospace; font-size:0.72rem; color:#38BDF8; background:rgba(56,189,248,0.15); border:1px solid rgba(56,189,248,0.35); padding:2px 8px; border-radius:10px;">{len(active_zones_list)} zones</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if active_zones_list:
            cards_html = []
            for iz in active_zones_list[:25]:
                dom_fleet_key = iz.get("dominant_fleet", "YELLOW")
                dom_color = {
                    "YELLOW": "#FACC15",
                    "GREEN":  "#22C55E",
                    "FHVHV":  "#A855F7",
                }.get(dom_fleet_key, "#38BDF8")

                fr = iz.get("fleet_ratios", {})
                fb = iz.get("fleet_breakdown", {})
                battle = iz.get("battle_status", "BALANCED")
                vc = iz.get("vehicle_count", 0)
                dom_pct = round(iz.get("dominance_ratio", 0) * 100)

                card_cls = "pm-card contested" if battle == "CONTESTED" else f"pm-card {dom_fleet_key.lower()}-dom"
                badge_text = "⚡ CONTESTED" if battle == "CONTESTED" else f"👑 {dom_fleet_key} {dom_pct}%"
                badge_bg = "rgba(234,179,8,0.2)" if battle == "CONTESTED" else "rgba(255,255,255,0.08)"
                badge_color = "#FDE047" if battle == "CONTESTED" else dom_color

                y_w = round(fr.get("YELLOW", 0) * 100)
                g_w = round(fr.get("GREEN", 0) * 100)
                h_w = round(fr.get("FHVHV", 0) * 100)

                card_str = (
                    f'<div class="{card_cls}">'
                    f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">'
                    f'<b style="font-size:0.88rem; color:#F8FAFC;">{iz.get("zone_name","Zone")}</b>'
                    f'<span style="font-family:\'JetBrains Mono\',monospace; font-size:0.72rem; color:{badge_color}; background:{badge_bg}; padding:2px 6px; border-radius:4px; font-weight:800;">{badge_text}</span>'
                    f'</div>'
                    f'<div style="font-size:0.78rem; color:#94A3B8; margin-bottom:6px;">{iz.get("borough","NYC")} · <span style="color:#38BDF8; font-weight:700;">{vc} vehicles</span></div>'
                    f'<div style="width:100%; height:6px; border-radius:3px; overflow:hidden; background:rgba(255,255,255,0.06); display:flex; margin-top:2px;">'
                    f'<div style="width:{y_w}%; background:#FACC15; height:100%;"></div>'
                    f'<div style="width:{g_w}%; background:#22C55E; height:100%;"></div>'
                    f'<div style="width:{h_w}%; background:#A855F7; height:100%;"></div>'
                    f'</div>'
                    f'<div style="display:flex; justify-content:space-between; font-size:0.68rem; color:#64748B; margin-top:3px; font-family:\'JetBrains Mono\',monospace;">'
                    f'<span>🚖 {fb.get("YELLOW",0)} ({y_w}%)</span>'
                    f'<span>🚕 {fb.get("GREEN",0)} ({g_w}%)</span>'
                    f'<span>📱 {fb.get("FHVHV",0)} ({h_w}%)</span>'
                    f'</div>'
                    f'</div>'
                )
                cards_html.append(card_str)

            full_feed_html = f'<div class="pm-feed-container">{"".join(cards_html)}</div>'
            st.markdown(full_feed_html, unsafe_allow_html=True)
        else:
            st.markdown(
                """
                <div style="padding:24px 16px; text-align:center; color:#64748B; background:rgba(15,23,42,0.5); border:1px dashed rgba(255,255,255,0.08); border-radius:10px;">
                  <div style="font-size:1.4rem; margin-bottom:8px;">🚕</div>
                  <div style="font-weight:700; color:#94A3B8; margin-bottom:4px;">No Active Vehicle Data</div>
                  <div style="font-size:0.78rem;">Active zones and contested battlegrounds will appear once vehicle telemetry is received.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ── TAB 4: 📊 Fleet Analytics ──────────────────────────────────────────────
with tab4:

    # ── CSS ────────────────────────────────────────────────────────────────
    st.markdown("""
    <style>
    .fa-scoreboard {
        background: rgba(15,23,42,0.85);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 14px;
        padding: 18px 20px 14px;
        position: relative;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .fa-scoreboard:hover { transform: translateY(-3px); box-shadow: 0 12px 32px rgba(0,0,0,0.4); }
    .fa-brand-title {
        font-size: 1.05rem; font-weight: 800; letter-spacing: 0.04em;
        display: flex; align-items: center; gap: 8px; margin-bottom: 14px;
    }
    .fa-metric-row {
        display: flex; justify-content: space-between; align-items: center;
        padding: 5px 0; border-bottom: 1px solid rgba(255,255,255,0.05);
        font-size: 0.82rem;
    }
    .fa-metric-row:last-child { border-bottom: none; }
    .fa-metric-label { color: #94A3B8; }
    .fa-metric-value { font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 0.88rem; }
    .fa-rank-badge {
        position: absolute; top: 12px; right: 14px;
        font-size: 1.3rem; line-height: 1;
    }
    .fa-section-header {
        font-size: 1.0rem; font-weight: 800; color: #F8FAFC;
        margin: 20px 0 10px; display: flex; align-items: center; gap: 8px;
    }
    .fa-section-divider {
        border: none; border-top: 1px solid rgba(255,255,255,0.07); margin: 18px 0;
    }
    </style>
    """, unsafe_allow_html=True)

    # ── Colour / display helpers ───────────────────────────────────────────
    _FA_META = {
        "YELLOW": {"icon": "🚖", "name": "Yellow Cab",        "hex": "#FACC15", "bg": "rgba(250,204,21,0.10)",  "border": "rgba(250,204,21,0.45)"},
        "GREEN":  {"icon": "🚕", "name": "Green Boro Taxi",   "hex": "#22C55E", "bg": "rgba(34,197,94,0.10)",   "border": "rgba(34,197,94,0.45)"},
        "FHVHV":  {"icon": "📱", "name": "FHVHV (Uber/Lyft)", "hex": "#A855F7", "bg": "rgba(168,85,247,0.10)", "border": "rgba(168,85,247,0.45)"},
    }
    _rank_medal = {0: "🥇", 1: "🥈", 2: "🥉"}
    _fleet_counts_t4 = {"YELLOW": y_cnt, "GREEN": g_cnt, "FHVHV": h_cnt}
    _fleet_zone_pct_t4 = {"YELLOW": y_pct, "GREEN": g_pct, "FHVHV": h_pct}

    # ── SECTION A: Head-to-Head Scoreboard ────────────────────────────────
    st.markdown('<div class="fa-section-header">🏆 Head-to-Head Scoreboard</div>', unsafe_allow_html=True)

    def _t4_composite(fk: str) -> float:
        fs = fleet_stats.get(fk, {})
        total_v = max(1, y_cnt + g_cnt + h_cnt)
        total_f = max(1, sum(s.get("total_fare", 0) for s in fleet_stats.values()))
        return (
            (_fleet_counts_t4.get(fk, 0) / total_v)              * 50
            + (fs.get("total_fare", 0) / total_f)                 * 35
            + (_fleet_zone_pct_t4.get(fk, 0) / 100.0)            * 15
        )

    _ranked = sorted(_FLEET_KEYS, key=_t4_composite, reverse=True)
    _score_cols = st.columns(3)

    for _medal_i, _fk in enumerate(_ranked):
        _m  = _FA_META[_fk]
        _fs = fleet_stats.get(_fk, {})
        _col_idx = _FLEET_KEYS.index(_fk)
        with _score_cols[_col_idx]:
            st.markdown(
                f"""<div class="fa-scoreboard" style="border-left:4px solid {_m['hex']}; background:{_m['bg']};">
                  <span class="fa-rank-badge">{_rank_medal[_medal_i]}</span>
                  <div class="fa-brand-title" style="color:{_m['hex']};">{_m['icon']} {_m['name']}</div>
                  <div class="fa-metric-row">
                    <span class="fa-metric-label">🚕 Active Vehicles</span>
                    <span class="fa-metric-value" style="color:{_m['hex']};">{_fleet_counts_t4[_fk]:,}</span>
                  </div>
                  <div class="fa-metric-row">
                    <span class="fa-metric-label">💰 Avg Fare</span>
                    <span class="fa-metric-value">${_fs.get('avg_fare', 0):.2f}</span>
                  </div>
                  <div class="fa-metric-row">
                    <span class="fa-metric-label">👥 Avg Passengers</span>
                    <span class="fa-metric-value">{_fs.get('avg_pax', 0):.1f}</span>
                  </div>
                  <div class="fa-metric-row">
                    <span class="fa-metric-label">🗺️ Zone Control</span>
                    <span class="fa-metric-value">{_fleet_zone_pct_t4.get(_fk, 0):.1f}%</span>
                  </div>
                </div>""",
                unsafe_allow_html=True,
            )

    st.markdown('<hr class="fa-section-divider">', unsafe_allow_html=True)

    # ── SECTION B: Borough Heatmap (PRIMARY) ──────────────────────────────
    st.markdown('<div class="fa-section-header">🗺️ Borough × Fleet Heatmap</div>', unsafe_allow_html=True)

    _hm_col, _radar_col = st.columns([3.5, 2])

    with _hm_col:
        _boroughs_present = [b for b in _BOROUGH_ORDER if b in borough_fleet_matrix]
        if not _boroughs_present:
            _boroughs_present = list(borough_fleet_matrix.keys())[:5]

        _hm_z = {
            fk: [borough_fleet_matrix.get(b, {}).get(fk, 0) for b in _boroughs_present]
            for fk in _FLEET_KEYS
        }
        _hm_total = [borough_fleet_matrix.get(b, {}).get("total", 0) for b in _boroughs_present]

        _hm_matrix  = [_hm_z["YELLOW"], _hm_z["GREEN"], _hm_z["FHVHV"]]
        _hm_ylabels = ["🚖 Yellow", "🚕 Green", "📱 FHVHV"]

        _hm_fig = go.Figure(go.Heatmap(
            z=_hm_matrix,
            x=_boroughs_present,
            y=_hm_ylabels,
            colorscale=[
                [0.0,  "rgba(15,23,42,0.9)"],
                [0.25, "rgba(56,189,248,0.3)"],
                [0.5,  "rgba(56,189,248,0.6)"],
                [0.75, "rgba(56,189,248,0.85)"],
                [1.0,  "rgba(14,165,233,1.0)"],
            ],
            showscale=True,
            colorbar=dict(
                title=dict(text="Vehicles", font=dict(color="#94A3B8", size=11)),
                tickfont=dict(color="#94A3B8", size=10),
                bgcolor="rgba(15,23,42,0.6)",
                bordercolor="rgba(255,255,255,0.08)",
                thickness=14,
            ),
            text=[[str(v) for v in row] for row in _hm_matrix],
            texttemplate="%{text}",
            textfont=dict(size=13, color="white", family="JetBrains Mono, monospace"),
            hoverongaps=False,
            hovertemplate="<b>%{x}</b> · %{y}<br>Vehicles: <b>%{z}</b><extra></extra>",
            xgap=3, ygap=3,
        ))
        _hm_fig.update_layout(
            height=240,
            margin=dict(l=0, r=0, t=30, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, sans-serif", color="#E2E8F0"),
            xaxis=dict(tickfont=dict(size=11, color="#CBD5E1"), showgrid=False, tickangle=-20),
            yaxis=dict(tickfont=dict(size=11, color="#CBD5E1"), showgrid=False),
            title=dict(text="Vehicle Count by Borough & Fleet Type", font=dict(size=13, color="#94A3B8"), x=0.0, xanchor="left"),
        )
        st.plotly_chart(_hm_fig, use_container_width=True)

        # Detailed annotated table below heatmap
        _dom_rows = []
        for _b in _boroughs_present:
            _bm   = borough_fleet_matrix.get(_b, {})
            _vals = {k: _bm.get(k, 0) for k in _FLEET_KEYS}
            _tot  = _bm.get("total", 0)
            _dom  = max(_vals, key=lambda k: _vals[k]) if any(_vals.values()) else None
            _dm   = _FA_META.get(_dom, {}) if _dom else {}
            _bar_y = round(_vals.get("YELLOW", 0) / max(1, _tot) * 100)
            _bar_g = round(_vals.get("GREEN",  0) / max(1, _tot) * 100)
            _bar_h = round(_vals.get("FHVHV",  0) / max(1, _tot) * 100)
            _dom_label = f"{_dm.get('icon','')}&nbsp;{_dom}" if _dom else "—"
            _dom_color = _dm.get("hex", "#94A3B8")
            _dom_rows.append(
                f'<tr style="border-bottom:1px solid rgba(255,255,255,0.05);">'
                f'<td style="padding:7px 10px;font-weight:700;color:#F8FAFC;">{_b}</td>'
                f'<td style="padding:7px 6px;font-family:\'JetBrains Mono\',monospace;color:#FACC15;">{_vals.get("YELLOW",0)}</td>'
                f'<td style="padding:7px 6px;font-family:\'JetBrains Mono\',monospace;color:#22C55E;">{_vals.get("GREEN",0)}</td>'
                f'<td style="padding:7px 6px;font-family:\'JetBrains Mono\',monospace;color:#A855F7;">{_vals.get("FHVHV",0)}</td>'
                f'<td style="padding:7px 6px;font-family:\'JetBrains Mono\',monospace;color:#38BDF8;font-weight:700;">{_tot}</td>'
                f'<td style="padding:7px 10px;">'
                f'  <div style="display:flex;gap:6px;align-items:center;">'
                f'    <div style="width:80px;height:7px;border-radius:4px;overflow:hidden;background:rgba(255,255,255,0.06);display:flex;">'
                f'      <div style="width:{_bar_y}%;background:#FACC15;"></div>'
                f'      <div style="width:{_bar_g}%;background:#22C55E;"></div>'
                f'      <div style="width:{_bar_h}%;background:#A855F7;"></div>'
                f'    </div>'
                f'    <span style="font-size:0.78rem;font-weight:800;color:{_dom_color};">{_dom_label}</span>'
                f'  </div>'
                f'</td>'
                f'</tr>'
            )

        st.markdown(
            f"""<div style="background:rgba(15,23,42,0.80);border:1px solid rgba(255,255,255,0.07);border-radius:12px;padding:10px 4px;margin-top:4px;overflow-x:auto;">
              <table style="width:100%;border-collapse:collapse;font-size:0.82rem;color:#E2E8F0;">
                <thead>
                  <tr style="border-bottom:2px solid rgba(255,255,255,0.1);">
                    <th style="padding:7px 10px;text-align:left;color:#94A3B8;font-weight:600;">Borough</th>
                    <th style="padding:7px 6px;text-align:left;color:#FACC15;font-weight:600;">🚖 Yellow</th>
                    <th style="padding:7px 6px;text-align:left;color:#22C55E;font-weight:600;">🚕 Green</th>
                    <th style="padding:7px 6px;text-align:left;color:#A855F7;font-weight:600;">📱 FHVHV</th>
                    <th style="padding:7px 6px;text-align:left;color:#38BDF8;font-weight:600;">Total</th>
                    <th style="padding:7px 10px;text-align:left;color:#94A3B8;font-weight:600;">Distribution &amp; Leader</th>
                  </tr>
                </thead>
                <tbody>{"".join(_dom_rows) if _dom_rows else '<tr><td colspan="6" style="text-align:center;padding:20px;color:#64748B;">Awaiting zone data…</td></tr>'}</tbody>
              </table>
            </div>""",
            unsafe_allow_html=True,
        )

    # ── SECTION C: Radar Chart ─────────────────────────────────────────────
    with _radar_col:
        st.markdown('<div class="fa-section-header" style="margin-top:0;">🕸️ Multi-Metric Profile</div>', unsafe_allow_html=True)

        _radar_dims = ["Fleet\nSize", "Total\nRev", "Avg\nFare", "Zone\nControl", "Avg\nPax"]

        # Raw values per fleet across 5 comparative dimensions
        _raw_vals_by_fleet = {
            _fk: [
                float(_fleet_counts_t4.get(_fk, 0)),
                float(fleet_stats[_fk].get("total_fare", 0)),
                float(fleet_stats[_fk].get("avg_fare",   0)),
                float(_fleet_zone_pct_t4.get(_fk, 0)),
                float(fleet_stats[_fk].get("avg_pax",    0)),
            ]
            for _fk in _FLEET_KEYS
        }

        # Normalize across fleets for EACH dimension independently (relative to max leader = 1.0)
        _r_vals_by_fleet = {k: [] for k in _FLEET_KEYS}
        for _di in range(len(_radar_dims)):
            _col_vals = [_raw_vals_by_fleet[_fk][_di] for _fk in _FLEET_KEYS]
            _mx = max(_col_vals) if max(_col_vals) > 0 else 1.0
            for _fk in _FLEET_KEYS:
                _r_vals_by_fleet[_fk].append(round(_raw_vals_by_fleet[_fk][_di] / _mx, 3))

        _radar_fig = go.Figure()
        for _fk in _FLEET_KEYS:
            _m  = _FA_META[_fk]
            _rv = _r_vals_by_fleet[_fk] + [_r_vals_by_fleet[_fk][0]]
            _rd = _radar_dims + [_radar_dims[0]]
            _hex = _m["hex"]
            _rgba_fill = f"rgba({int(_hex[1:3],16)},{int(_hex[3:5],16)},{int(_hex[5:7],16)},0.15)"
            _radar_fig.add_trace(go.Scatterpolar(
                r=_rv, theta=_rd,
                fill="toself", fillcolor=_rgba_fill,
                line=dict(color=_hex, width=2),
                name=f"{_m['icon']} {_m['name']}",
                hovertemplate=f"<b>{_m['name']}</b><br>%{{theta}}: <b>%{{r:.0%}}</b><extra></extra>",
            ))

        _radar_fig.update_layout(
            polar=dict(
                bgcolor="rgba(15,23,42,0.6)",
                radialaxis=dict(visible=True, range=[0, 1], tickformat=".0%",
                                tickfont=dict(size=9, color="#64748B"),
                                gridcolor="rgba(255,255,255,0.06)", linecolor="rgba(255,255,255,0.06)"),
                angularaxis=dict(tickfont=dict(size=10, color="#CBD5E1"),
                                 gridcolor="rgba(255,255,255,0.08)", linecolor="rgba(255,255,255,0.08)"),
            ),
            showlegend=True,
            legend=dict(orientation="h", y=-0.12, x=0.5, xanchor="center",
                        font=dict(size=10, color="#CBD5E1"), bgcolor="rgba(0,0,0,0)"),
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=30, r=30, t=10, b=50),
            height=380,
        )
        st.plotly_chart(_radar_fig, use_container_width=True)

    st.markdown('<hr class="fa-section-divider">', unsafe_allow_html=True)

    # ── SECTION D: Passenger Load Breakdown ────────────────────────────────
    st.markdown('<div class="fa-section-header">👥 Passenger Load Breakdown &amp; Occupancy Profile</div>', unsafe_allow_html=True)

    _pax_buckets = ["1 Pax (Solo)", "2 Pax (Duo)", "3–4 Pax (Group)", "5+ Pax (Family/Van)"]
    _pax_counts_by_fleet: dict[str, list[int]] = {}
    _pax_shares_by_fleet: dict[str, list[float]] = {}

    for _fk in _FLEET_KEYS:
        _vlist = _fleet_vehicles.get(_fk, [])
        _p_list = [int(v.get("passenger_count", 1) or 1) for v in _vlist]
        _b1 = sum(1 for p in _p_list if p <= 1)
        _b2 = sum(1 for p in _p_list if p == 2)
        _b3 = sum(1 for p in _p_list if 3 <= p <= 4)
        _b4 = sum(1 for p in _p_list if p >= 5)
        _counts = [_b1, _b2, _b3, _b4]
        _tot_p = max(1, sum(_counts))
        _pax_counts_by_fleet[_fk] = _counts
        _pax_shares_by_fleet[_fk] = [round(c / _tot_p * 100, 1) for c in _counts]

    _pax_col1, _pax_col2 = st.columns(2)

    with _pax_col1:
        st.markdown('<div style="font-size:0.85rem;font-weight:700;color:#94A3B8;margin-bottom:6px;">📊 Active Trips by Passenger Group</div>', unsafe_allow_html=True)
        _pax_fig1 = go.Figure()
        for _fk in _FLEET_KEYS:
            _m = _FA_META[_fk]
            _hex = _m["hex"]
            _counts = _pax_counts_by_fleet[_fk]
            _pax_fig1.add_trace(go.Bar(
                name=f"{_m['icon']} {_m['name']}",
                x=_pax_buckets,
                y=_counts,
                marker=dict(color=_hex, opacity=0.88, line=dict(color="rgba(255,255,255,0.12)", width=1)),
                text=[f"{c:,}" if c > 0 else "" for c in _counts],
                textposition="auto",
                textfont=dict(size=11, color="white", family="JetBrains Mono, monospace"),
                hovertemplate=f"<b>{_m['name']}</b><br>%{{x}}: <b>%{{y:,}} trips</b><extra></extra>",
            ))

        _pax_fig1.update_layout(
            barmode="group",
            height=300,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(15,23,42,0.4)",
            margin=dict(l=10, r=10, t=10, b=50),
            font=dict(family="Inter, sans-serif", color="#E2E8F0"),
            legend=dict(
                orientation="h",
                y=-0.22,
                x=0.5,
                xanchor="center",
                font=dict(size=10, color="#CBD5E1"),
                bgcolor="rgba(0,0,0,0)",
            ),
            xaxis=dict(showgrid=False, tickfont=dict(size=10, color="#CBD5E1")),
            yaxis=dict(
                gridcolor="rgba(255,255,255,0.05)",
                tickfont=dict(size=9, color="#64748B"),
                title=dict(text="Active Trips", font=dict(size=10, color="#64748B")),
            ),
        )
        st.plotly_chart(_pax_fig1, use_container_width=True)

    with _pax_col2:
        st.markdown('<div style="font-size:0.85rem;font-weight:700;color:#94A3B8;margin-bottom:6px;">📈 Occupancy Mix Share (100% Normalized)</div>', unsafe_allow_html=True)
        _pax_fig2 = go.Figure()
        _tier_colors = ["#38BDF8", "#818CF8", "#F59E0B", "#EC4899"]
        _fleet_display_names = [f"{_FA_META[k]['icon']} {_FA_META[k]['name']}" for k in _FLEET_KEYS]

        for _ti, _tier_name in enumerate(_pax_buckets):
            _tier_shares = [_pax_shares_by_fleet[k][_ti] for k in _FLEET_KEYS]
            _tier_counts = [_pax_counts_by_fleet[k][_ti] for k in _FLEET_KEYS]
            _pax_fig2.add_trace(go.Bar(
                name=_tier_name,
                y=_fleet_display_names,
                x=_tier_shares,
                orientation="h",
                marker=dict(color=_tier_colors[_ti], opacity=0.88, line=dict(color="rgba(255,255,255,0.08)", width=1)),
                text=[f"{s:.0f}%" if s >= 6 else "" for s in _tier_shares],
                textposition="inside",
                textfont=dict(size=10, color="white", family="JetBrains Mono, monospace"),
                hovertemplate=f"<b>%{{y}}</b><br>{_tier_name}: <b>%{{x:.1f}}%</b> (%{{customdata:,}} trips)<extra></extra>",
                customdata=_tier_counts,
            ))

        _pax_fig2.update_layout(
            barmode="stack",
            height=300,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(15,23,42,0.4)",
            margin=dict(l=10, r=10, t=10, b=50),
            font=dict(family="Inter, sans-serif", color="#E2E8F0"),
            legend=dict(
                orientation="h",
                y=-0.22,
                x=0.5,
                xanchor="center",
                font=dict(size=10, color="#CBD5E1"),
                bgcolor="rgba(0,0,0,0)",
            ),
            xaxis=dict(gridcolor="rgba(255,255,255,0.05)", tickfont=dict(size=9, color="#64748B"), ticksuffix="%"),
            yaxis=dict(showgrid=False, tickfont=dict(size=11, color="#E2E8F0")),
        )
        st.plotly_chart(_pax_fig2, use_container_width=True)


