# src/routing/graphs.py
from __future__ import annotations
import os
import osmnx as ox

CACHE_DIR = "outputs/osm_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def _cache_path(network_type: str, buffer_m: int) -> str:
    return os.path.join(CACHE_DIR, f"nyc_{network_type}_{buffer_m}m.graphml")

def get_local_graph(network_type: str, center_lat: float, center_lon: float, buffer_m: int = 4000):
    """
    Builds a local OSM graph around a point to keep routing fast + stable.
    network_type: 'drive' or 'bike'
    """
    path = _cache_path(network_type, buffer_m)
    if os.path.exists(path):
        return ox.load_graphml(path)

    G = ox.graph_from_point((center_lat, center_lon), dist=buffer_m, network_type=network_type)
    G = ox.add_edge_speeds(G)
    G = ox.add_edge_travel_times(G)
    ox.save_graphml(G, path)
    return G
