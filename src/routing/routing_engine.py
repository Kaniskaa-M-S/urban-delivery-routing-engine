# src/routing/routing_engine.py
from __future__ import annotations

import math
import os
import inspect
from typing import Dict, Any, Tuple

import osmnx as ox
import networkx as nx
import pandas as pd

from src.model.feasibility import check_mode_feasible_from_route
from src.model.mode_params import build_mode_params


# -------------------------
# Geometry helpers
# -------------------------

def haversine_m(lat1, lon1, lat2, lon2) -> float:
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def compute_center_and_radius_m(o_lat, o_lon, d_lat, d_lon, pad_km=3.0) -> Tuple[float, float, float]:
    """
    Local OSM subgraph around midpoint.
    radius = half great-circle distance + padding.
    """
    dist_m = haversine_m(o_lat, o_lon, d_lat, d_lon)
    center_lat = (o_lat + d_lat) / 2
    center_lon = (o_lon + d_lon) / 2
    radius_m = (dist_m / 2) + pad_km * 1000.0
    radius_m = min(max(radius_m, 3000.0), 20000.0)
    return center_lat, center_lon, radius_m


# -------------------------
# OSM graph + route helpers
# -------------------------

def load_local_graph(center_lat: float, center_lon: float, radius_m: float, network_type: str):
    """
    Build a local graph around midpoint. (Streamlit caches higher up if you wrap it.)
    """
    G = ox.graph_from_point(
        (center_lat, center_lon),
        dist=radius_m,
        network_type=network_type,
        simplify=True,
        retain_all=False,
        truncate_by_edge=True,
    )
    G = ox.distance.add_edge_lengths(G)
    G = ox.add_edge_speeds(G)
    G = ox.add_edge_travel_times(G)
    return G


def shortest_route_nodes(G, origin_lat, origin_lon, dest_lat, dest_lon, weight="travel_time"):
    o_node = ox.distance.nearest_nodes(G, origin_lon, origin_lat)
    d_node = ox.distance.nearest_nodes(G, dest_lon, dest_lat)
    route = nx.shortest_path(G, o_node, d_node, weight=weight)
    return route


def route_distance_time(G, route_nodes) -> Tuple[float, float]:
    """
    Returns (dist_km, time_min) for the route nodes.
    """
    gdf_edges = ox.routing.route_to_gdf(G, route_nodes, weight="length")
    dist_m = float(gdf_edges["length"].sum())
    if "travel_time" in gdf_edges.columns:
        time_s = float(gdf_edges["travel_time"].sum())
    else:
        time_s = float(nx.path_weight(G, route_nodes, weight="travel_time"))
    return dist_m / 1000.0, time_s / 60.0


def _norm_mode(s: str) -> str:
    return str(s).strip().lower().replace("-", "_").replace(" ", "_")


# -------------------------
# Mode params loader (robust)
# -------------------------

def _safe_build_mode_params() -> pd.DataFrame:
    """
    Calls build_mode_params even if it requires file paths.
    If it fails, returns a minimal default table so UI can still run.
    """
    try:
        sig = inspect.signature(build_mode_params)
        params = list(sig.parameters.keys())

        # If no args required
        if len(params) == 0:
            return build_mode_params()

        # Try to pass expected cleaned data paths by name
        base = os.getcwd()
        cleaned = os.path.join(base, "Cleaned Data")
        perf_default = os.path.join(cleaned, "Mode_performance_parameters.xlsx")
        cost_default = os.path.join(cleaned, "Mode_cost_parameters.xlsx")

        kwargs = {}
        for p in params:
            pl = p.lower()
            if "perf" in pl:
                kwargs[p] = perf_default
            if "cost" in pl:
                kwargs[p] = cost_default

        return build_mode_params(**kwargs)

    except Exception:
        # Fallback defaults (calibrate later)
        return pd.DataFrame([
            {
                "mode": "truck",
                "speed_kmph": 25,
                "emissions_per_km": 1.2,
                "max_service_radius_km": 40,
                "max_parcels_per_day": 500,
                "congestion_sensitivity": 1.0,
                "cost_per_km": 2.5,
                "curb_penalty_min": 8,
                "service_time_min_per_parcel": 0.15,
            },
            {
                "mode": "e-van",
                "speed_kmph": 25,
                "emissions_per_km": 0.4,
                "max_service_radius_km": 35,
                "max_parcels_per_day": 350,
                "congestion_sensitivity": 0.9,
                "cost_per_km": 1.8,
                "curb_penalty_min": 4,
                "service_time_min_per_parcel": 0.12,
            },
            {
                "mode": "cargo bike",
                "speed_kmph": 15,
                "emissions_per_km": 0.0,
                "max_service_radius_km": 10,
                "max_parcels_per_day": 80,
                "congestion_sensitivity": 0.6,
                "cost_per_km": 0.6,
                "curb_penalty_min": 1,
                "service_time_min_per_parcel": 0.18,
            },
        ])


# -------------------------
# Main Engine
# -------------------------

def compute_multimodal_routes(
    o_lat: float,
    o_lon: float,
    d_lat: float,
    d_lon: float,
    buffer_km: float,
    weight_key: str = "travel_time",
    demand_parcels: float = 30.0,
    congestion_level: str = "medium",
    disruptive_event: str = "normal",
) -> Dict[str, Any]:
    """
    Returns:
      {
        "meta": {...},
        "graphs": {"drive": G_drive, "bike": G_bike},
        "modes": {
           "truck": {...},
           "e_van": {...},
           "cargo_bike": {...},
        }
      }
    """

    center_lat, center_lon, radius_m = compute_center_and_radius_m(o_lat, o_lon, d_lat, d_lon, pad_km=buffer_km)

    G_drive = load_local_graph(center_lat, center_lon, radius_m, "drive")
    G_bike = load_local_graph(center_lat, center_lon, radius_m, "bike")

    mode_df = _safe_build_mode_params().copy()
    mode_df["mode_norm"] = mode_df["mode"].apply(_norm_mode)

    # Ensure penalty columns exist (prevents KeyError)
    if "curb_penalty_min" not in mode_df.columns:
        mode_df["curb_penalty_min"] = 0.0
    if "service_time_min_per_parcel" not in mode_df.columns:
        mode_df["service_time_min_per_parcel"] = 0.0

    out: Dict[str, Any] = {
        "meta": {
            "center_lat": center_lat,
            "center_lon": center_lon,
            "radius_m": radius_m,
            "weight_key": weight_key,
            "demand_parcels": demand_parcels,
            "congestion_level": congestion_level,
            "disruptive_event": disruptive_event,
        },
        "graphs": {"drive": G_drive, "bike": G_bike},
        "modes": {},
    }

    mode_map = {
        "truck": ("drive", G_drive),
        "e_van": ("drive", G_drive),
        "cargo_bike": ("bike", G_bike),
    }

    for mode_key, (net_type, G) in mode_map.items():
        # match mode row
        candidates = [mode_key, mode_key.replace("_", " "), mode_key.replace("_", "-")]
        row = None
        for c in candidates:
            r = mode_df.loc[mode_df["mode_norm"] == _norm_mode(c)]
            if len(r) > 0:
                row = r.iloc[0]
                break

        if row is None:
            out["modes"][mode_key] = {"error": f"Mode '{mode_key}' not found in mode parameters."}
            continue

        # compute route
        try:
            route_nodes = shortest_route_nodes(G, o_lat, o_lon, d_lat, d_lon, weight=weight_key)
            dist_km, route_time_min = route_distance_time(G, route_nodes)
        except Exception as e:
            out["modes"][mode_key] = {"error": f"Routing failed for {mode_key}: {e}"}
            continue

        # feasibility + multipliers
        feasible, reason, speed_mult, cost_mult = check_mode_feasible_from_route(
            dist_km=dist_km,
            demand_parcels=demand_parcels,
            congestion_level=congestion_level,
            disruptive_event=disruptive_event,
            mode_row=row,
        )

        curb_penalty_min = float(row.get("curb_penalty_min", 0.0))
        service_time_min_per_parcel = float(row.get("service_time_min_per_parcel", 0.0))

        # effective time
        if not feasible or speed_mult <= 0:
            effective_time_min = float("inf")
        else:
            adjusted_route_min = route_time_min * (1.0 / max(speed_mult, 1e-6))
            effective_time_min = adjusted_route_min + curb_penalty_min + demand_parcels * service_time_min_per_parcel

        out["modes"][mode_key] = {
            "network_type": net_type,
            "route_nodes": route_nodes,
            "dist_km": dist_km,
            "route_time_min": route_time_min,
            "feasible": bool(feasible),
            "max_service_radius_km": float(row.get("max_service_radius_km", float("nan"))),

            "reason": reason,
            "speed_multiplier": float(speed_mult),
            "cost_multiplier": float(cost_mult),
            "curb_penalty_min": curb_penalty_min,
            "service_time_min_per_parcel": service_time_min_per_parcel,
            "effective_time_min": effective_time_min,
        }

    return out
