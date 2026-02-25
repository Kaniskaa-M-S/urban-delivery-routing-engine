# app.py
import math
import streamlit as st
import pandas as pd
import osmnx as ox
import folium
from streamlit_folium import st_folium

# NEW: call the routing engine
from src.routing.routing_engine import compute_multimodal_routes

# ---------------------------------------------------------
# Page / App config
# ---------------------------------------------------------
st.set_page_config(page_title="NYC Multi-Modal Routing", layout="wide")

NTA_CSV = "Cleaned Data/NTA_spatial_inputs_WGS84.csv"
DISPATCH_CSV = "Cleaned Data/dispatch_centers_WGS84.csv"

LAT_CANDIDATES = ["cent_lat", "cent_lat_dd", "lat", "latitude", "y", "LAT", "Latitude", "Y"]
LON_CANDIDATES = ["cent_lon", "cent_lon_dd", "lon", "longitude", "x", "LON", "Longitude", "X"]

# 3 distinct colors
COLOR_TRUCK = "#ff7f0e"  # orange
COLOR_EV    = "#2ca02c"  # green
COLOR_BIKE  = "#1f77b4"  # blue

# Make OSMnx quieter + faster a bit
ox.settings.log_console = False
ox.settings.use_cache = True

# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------
def find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    cols_lower = {c.lower(): c for c in df.columns}
    for cand in candidates:
        key = cand.lower()
        if key in cols_lower:
            return cols_lower[key]
    return None

def require_cols(df: pd.DataFrame, required: list[str], name: str):
    missing = [c for c in required if c not in df.columns]
    if missing:
        st.error(f"{name} is missing columns: {missing}\n\nColumns found: {list(df.columns)}")
        st.stop()

@st.cache_data
def load_data():
    nta = pd.read_csv(NTA_CSV)
    disp = pd.read_csv(DISPATCH_CSV)

    nta_lat = find_col(nta, LAT_CANDIDATES)
    nta_lon = find_col(nta, LON_CANDIDATES)

    disp_lat = find_col(disp, ["lat", "latitude", "y", "LAT", "Latitude", "Y"])
    disp_lon = find_col(disp, ["lon", "longitude", "x", "LON", "Longitude", "X"])

    if not nta_lat or not nta_lon:
        st.error(
            f"Could not find latitude/longitude columns in {NTA_CSV}.\n\n"
            f"Columns: {list(nta.columns)}\n\n"
            f"Expected LAT in {LAT_CANDIDATES} and LON in {LON_CANDIDATES}"
        )
        st.stop()

    if not disp_lat or not disp_lon:
        st.error(
            f"Could not find latitude/longitude columns in {DISPATCH_CSV}.\n\n"
            f"Columns: {list(disp.columns)}\n\n"
            f"Expected typical columns like lat/lon (or latitude/longitude)."
        )
        st.stop()

    nta = nta.copy()
    disp = disp.copy()

    nta["LAT"] = pd.to_numeric(nta[nta_lat], errors="coerce")
    nta["LON"] = pd.to_numeric(nta[nta_lon], errors="coerce")
    disp["LAT"] = pd.to_numeric(disp[disp_lat], errors="coerce")
    disp["LON"] = pd.to_numeric(disp[disp_lon], errors="coerce")

    require_cols(nta, ["NTA2020", "NTAName", "LAT", "LON"], "NTA file")

    if "Dispatch_name" not in disp.columns:
        name_col = next((c for c in disp.columns if "name" in c.lower()), None)
        disp["Dispatch_name"] = disp[name_col] if name_col else ["Dispatch"] * len(disp)

    nta = nta.dropna(subset=["LAT", "LON"])
    disp = disp.dropna(subset=["LAT", "LON"])

    nta["NTA_LABEL"] = nta["NTA2020"].astype(str) + " — " + nta["NTAName"].astype(str)

    return nta, disp

def add_route_geometry(m, G, route, color, weight, name, show_nodes=False, dash_array=None):
    """
    Draw street-following route using edge geometries.
    Also optionally draw route nodes as visible dots.
    """
    gdf_edges = ox.routing.route_to_gdf(G, route, weight="length")  # geometry doesn't depend on weight

    for geom in gdf_edges.geometry:
        if geom is None:
            continue

        def draw_linestring(linestring):
            coords = [(lat, lon) for lon, lat in list(linestring.coords)]
            folium.PolyLine(
                coords,
                color=color,
                weight=weight,
                opacity=0.9,
                tooltip=name,
                dash_array=dash_array,
            ).add_to(m)

        if geom.geom_type == "LineString":
            draw_linestring(geom)
        elif geom.geom_type == "MultiLineString":
            for part in geom.geoms:
                draw_linestring(part)

    if show_nodes:
        for n in route:
            folium.CircleMarker(
                location=(G.nodes[n]["y"], G.nodes[n]["x"]),
                radius=5,
                weight=2,
                color=color,
                fill=True,
                fill_opacity=1.0,
                opacity=1.0,
            ).add_to(m)

def add_network_overlay(m, G, max_edges=6000, color="#888888", weight=1, opacity=0.45):
    """
    Optional: draw a downsampled set of network edges.
    """
    edges = ox.graph_to_gdfs(G, nodes=False, fill_edge_geometry=True)
    if len(edges) > max_edges:
        edges = edges.sample(max_edges, random_state=1)

    for geom in edges.geometry:
        if geom is None:
            continue

        def draw_linestring(linestring):
            coords = [(lat, lon) for lon, lat in list(linestring.coords)]
            folium.PolyLine(coords, color=color, weight=weight, opacity=opacity).add_to(m)

        if geom.geom_type == "LineString":
            draw_linestring(geom)
        elif geom.geom_type == "MultiLineString":
            for part in geom.geoms:
                draw_linestring(part)

def fmt_time(x):
    if x is None:
        return "—"
    try:
        if isinstance(x, float) and math.isinf(x):
            return "∞"
        return f"{float(x):.1f}"
    except Exception:
        return "—"

# ---------------------------------------------------------
# UI
# ---------------------------------------------------------
st.title("NYC Multi-Modal Routing Demo (Truck • E-Van • Cargo Bike)")
st.caption("Select a dispatch center and destination NTA centroid. Routes follow OpenStreetMap street geometries.")

nta_df, disp_df = load_data()

left, right = st.columns([1, 2], gap="large")

with left:
    st.subheader("Inputs")

    dispatch_name = st.selectbox("Dispatch center", disp_df["Dispatch_name"].tolist(), index=0)
    disp_row = disp_df.loc[disp_df["Dispatch_name"] == dispatch_name].iloc[0]
    o_lat, o_lon = float(disp_row["LAT"]), float(disp_row["LON"])

    nta_choice = st.selectbox("Destination NTA", nta_df["NTA_LABEL"].tolist(), index=0)
    nta_code = nta_choice.split(" — ")[0]
    dest_row = nta_df.loc[nta_df["NTA2020"].astype(str) == str(nta_code)].iloc[0]
    d_lat, d_lon = float(dest_row["LAT"]), float(dest_row["LON"])

    st.divider()

    pad_km = st.slider("OSM graph buffer (km)", 1.0, 12.0, 4.0, 0.5)

    weight_mode = st.radio(
        "Optimize for",
        ["Travel time (baseline)", "Distance (simple)"],
        index=0,
    )
    weight_key = "travel_time" if weight_mode.startswith("Travel time") else "length"

    show_nodes   = st.checkbox("Show route nodes (dots)", value=False)
    show_network = st.checkbox("Show network edges (heavy)", value=False)
    show_feasibility = st.checkbox("Show feasibility boundaries", value=True)

    st.divider()
    st.subheader("Delivery assumptions (minimal)")

    # These are not “random knobs” — they are required to activate feasibility + effective time logic.
    demand_parcels = st.slider("Parcels (for this tour)", 1, 200, 30, 1)

    congestion_level = st.selectbox("Congestion", ["low", "medium", "high"], index=1)
    disruptive_event = st.selectbox("Weather/Disruption", ["normal", "rain", "snow", "heatwave"], index=0)

    st.caption("If it’s slow: lower buffer + keep network overlay off.")

with right:
    st.subheader("Map + Routes")

    # -----------------------------
    # Core engine call (NEW)
    # -----------------------------
    results = compute_multimodal_routes(
        o_lat=o_lat,
        o_lon=o_lon,
        d_lat=d_lat,
        d_lon=d_lon,
        buffer_km=pad_km,
        weight_key=weight_key,
        demand_parcels=float(demand_parcels),
        congestion_level=str(congestion_level),
        disruptive_event=str(disruptive_event),
    )

    center_lat = results["meta"]["center_lat"]
    center_lon = results["meta"]["center_lon"]

    G_drive = results["graphs"]["drive"]
    G_bike  = results["graphs"]["bike"]

    # Pull routes for drawing
    truck_route = results["modes"]["truck"].get("route_nodes", [])
    ev_route    = results["modes"]["e_van"].get("route_nodes", [])
    bike_route  = results["modes"]["cargo_bike"].get("route_nodes", [])

    # Base map
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles="CartoDB positron")

    # Optional: show BOTH networks (drive + bike)
    if show_network:
        add_network_overlay(m, G_drive, max_edges=6000, color="#888888", weight=1, opacity=0.45)
        add_network_overlay(m, G_bike,  max_edges=6000, color="#666666", weight=1, opacity=0.25)

    # Markers
    folium.Marker(
        [o_lat, o_lon],
        tooltip=f"Dispatch: {dispatch_name}",
        icon=folium.Icon(color="blue"),
    ).add_to(m)

    folium.Marker(
        [d_lat, d_lon],
        tooltip=f"Dest NTA: {nta_code}",
        icon=folium.Icon(color="red"),
    ).add_to(m)

    # Feasibility boundaries (service radius circles)
if show_feasibility:
    boundary_styles = {
        "truck": (COLOR_TRUCK, None),
        "e_van": (COLOR_EV, "6,10"),
        "cargo_bike": (COLOR_BIKE, None),
    }

    for mode_key, (col, dash) in boundary_styles.items():
        mr = results["modes"].get(mode_key, {})
        if "error" in mr:
            continue

        r_km = mr.get("max_service_radius_km", None)
        if r_km is None:
            continue
        if isinstance(r_km, float) and math.isnan(r_km):
            continue

        folium.Circle(
            location=(o_lat, o_lon),
            radius=float(r_km) * 1000.0,
            color=col,
            weight=2,
            opacity=0.8,
            fill=False,
            dash_array=dash,
            tooltip=f"{mode_key}: max service radius {float(r_km):.1f} km",
        ).add_to(m)


    # Draw routes (only if routing succeeded)
    if truck_route:
        add_route_geometry(m, G_drive, truck_route, COLOR_TRUCK, 7, "Truck (drive)", show_nodes=show_nodes, dash_array=None)
    if ev_route:
        add_route_geometry(m, G_drive, ev_route,    COLOR_EV,    5, "E-Van (drive)", show_nodes=show_nodes, dash_array="6,10")
    if bike_route:
        add_route_geometry(m, G_bike,  bike_route,  COLOR_BIKE,  6, "Cargo Bike (bike)", show_nodes=show_nodes, dash_array=None)

    st_folium(m, width=980, height=560)

    # Metrics
    st.markdown("### Route metrics (ops-aware)")

    rows = []
    for key, label in [("truck", "Truck"), ("e_van", "E-Van"), ("cargo_bike", "Cargo Bike")]:
        mres = results["modes"].get(key, {})

        # --- ERROR ROW: must still have 9 cells
        if "error" in mres:
            rows.append([label, "ERROR", mres["error"], "—", "—", "—", "—", "—", "—"])
            continue

        maxr = mres.get("max_service_radius_km", None)
        maxr_str = "—"
        try:
            if maxr is not None and not (isinstance(maxr, float) and math.isnan(maxr)):
                maxr_str = f"{float(maxr):.1f}"
        except Exception:
            pass

        rows.append([
            label,
            "Yes" if mres.get("feasible") else "No",
            mres.get("reason", "—"),
            maxr_str,
            f"{mres.get('dist_km', 0.0):.2f}",
            f"{mres.get('route_time_min', 0.0):.1f}",
            fmt_time(mres.get("effective_time_min")),
            f"{mres.get('speed_multiplier', 1.0):.2f}",
            f"{mres.get('curb_penalty_min', 0.0):.1f}",
        ])


    df = pd.DataFrame(
        rows,
        columns = [
        "Mode",
        "Feasible",
        "Reason",
        "Max radius (km)",
        "Distance (km)",
        "Route time (min)",
        "Effective delivery time (min)",
        "Speed multiplier",
        "Curb penalty (min)",
    ]
    
    )
    st.dataframe(df, use_container_width=True)

    st.caption(
        "Baseline note: OSMnx travel_time uses OSM maxspeed tags where available and defaults where missing. "
        "Congestion/weather are applied as multipliers; curb penalties approximate stop/parking friction. "
        "Truck vs e-van will be identical until we add mode-specific constraints/weights."
    )
