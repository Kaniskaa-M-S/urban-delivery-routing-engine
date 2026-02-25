# src/routing/route.py
from __future__ import annotations
import osmnx as ox
import networkx as nx

def shortest_route(G, orig_lat, orig_lon, dest_lat, dest_lon, weight="length"):
    o = ox.distance.nearest_nodes(G, X=orig_lon, Y=orig_lat)
    d = ox.distance.nearest_nodes(G, X=dest_lon, Y=dest_lat)
    route_nodes = nx.shortest_path(G, o, d, weight=weight)
    gdf_edges = ox.routing.route_to_gdf(G, route_nodes, weight=weight)

    dist_m = float(gdf_edges["length"].sum())
    time_s = float(gdf_edges["travel_time"].sum()) if "travel_time" in gdf_edges.columns else None
    return gdf_edges, dist_m, time_s

def route_metrics_km_min(G, orig_lat, orig_lon, dest_lat, dest_lon):
    _, dist_m, time_s = shortest_route(G, orig_lat, orig_lon, dest_lat, dest_lon, weight="travel_time")
    return dist_m / 1000.0, (time_s / 60.0 if time_s is not None else None)
