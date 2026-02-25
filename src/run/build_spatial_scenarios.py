from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from math import radians, sin, cos, sqrt, atan2

# -------------------------
# Helpers
# -------------------------
def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance in km between two (lat, lon) points in decimal degrees."""
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

def assert_latlon(df: pd.DataFrame, lat_col: str, lon_col: str, name: str) -> None:
    lat = df[lat_col].astype(float)
    lon = df[lon_col].astype(float)
    if not ((lat.between(-90, 90)).all() and (lon.between(-180, 180)).all()):
        bad = df.loc[~(lat.between(-90, 90) & lon.between(-180, 180)), [lat_col, lon_col]].head(5)
        raise ValueError(
            f"{name} coordinates do NOT look like lat/lon decimal degrees.\n"
            f"Check ArcGIS export. Example bad rows:\n{bad}"
        )

def normalize(series: pd.Series) -> pd.Series:
    # Coerce anything weird to NaN
    s = pd.to_numeric(series, errors="coerce")

    # If everything is NaN, return 1s
    if s.notna().sum() == 0:
        return pd.Series(np.ones(len(s)), index=s.index)

    m = np.nanmedian(s)

    # Guard bad median (0 or NaN)
    if (m is None) or np.isnan(m) or m == 0:
        return pd.Series(np.ones(len(s)), index=s.index)

    out = s / m

    # Replace inf/-inf with NaN then fill to 1
    out = out.replace([np.inf, -np.inf], np.nan).fillna(1.0)
    return out
# -------------------------
# Main
# -------------------------
def main(nta_csv: Path, dispatch_csv: Path, out_csv: Path, pairing: str, network_factor: float, base_demand: float):
    nta = pd.read_csv(nta_csv)
    disp = pd.read_csv(dispatch_csv)

    # ---- REQUIRED: rename/standardize columns (edit here if your headers differ) ----
    # NTA expected columns
    NTA_ID = "NTA2020"
    BORO  = "BoroName"
    LAT   = "cent_lat_dd"   # <-- from ArcGIS fix step
    LON   = "cent_lon_dd"   # <-- from ArcGIS fix step
    SPEED = "speed_mult"    # already in your NTA export
    AADT_CLASS = "AADT_class"

    # Demand proxy field (use what you already computed)
    # You said: "MEDIAN_AADT_St_12" is your median single-unit truck AADT field
    DEMAND_PROXY = "MEDIAN_AADT_St_12"

    # Dispatch expected columns (from your screenshot)
    DISP_NAME = "Name"
    DISP_CLUSTER = "Cluster_id"   # borough/cluster label
    DISP_LAT = "Latitude"
    DISP_LON = "Longitude"

    # Basic sanity
    for col in [NTA_ID, BORO, LAT, LON, SPEED, DEMAND_PROXY]:
        if col not in nta.columns:
            raise KeyError(f"NTA file missing required column: {col}")

    for col in [DISP_NAME, DISP_CLUSTER, DISP_LAT, DISP_LON]:
        if col not in disp.columns:
            raise KeyError(f"Dispatch file missing required column: {col}")

    assert_latlon(nta, LAT, LON, "NTA")
    assert_latlon(disp, DISP_LAT, DISP_LON, "Dispatch")

    # Clean
    nta = nta.copy()
    disp = disp.copy()

    nta["Borough"] = nta[BORO].astype(str)
    disp["Dispatch_name"] = disp[DISP_NAME].astype(str)
    disp["Dispatch_cluster_id"] = disp[DISP_CLUSTER].astype(str)

    # ---- Demand: turn your truck-AADT proxy into parcels/day (relative scaling) ----
    # This is honest + defensible: "parcels proportional to freight activity proxy"
    # ---- Demand: turn your truck-AADT proxy into parcels/day (relative scaling) ----
    # Interpretation: parcels handled by *your microhub system* in that NTA (not total neighborhood parcels)
    # because the feasibility engine is single-vehicle/day capacity based.

    proxy = pd.to_numeric(nta[DEMAND_PROXY], errors="coerce")
    p05, p95 = proxy.quantile([0.05, 0.95])

    # scale into 0..1 using robust quantiles
    scaled = (proxy - p05) / (p95 - p05)
    scaled = scaled.clip(0, 1)

    # now map 0..1 -> 0.3..3.0
    demand_factor = 0.3 + scaled * 2.7


    # 1) Total-demand proxy (still relative)
    raw_total = (base_demand * demand_factor).round(0)
    raw_total = raw_total.replace([np.inf, -np.inf], np.nan).fillna(base_demand)

    # 2) Convert "total neighborhood demand" -> "demand served by our system"
    MARKET_SHARE = 0.10   # 10% pilot capture (change to 0.05–0.20 as a sensitivity)
    raw_system = (raw_total * MARKET_SHARE)

    # 3) Clamp to match your per-vehicle/day capacity scale (Truck~160, Van~140, Bike~80)
    # You want meaningful variation without collapsing everywhere.
    raw_system = raw_system.clip(20, 180)

    nta["Demand_parcels_per_day"] = raw_system.round(0).astype(int)

    print("Demand proxy NA count:", pd.to_numeric(nta[DEMAND_PROXY], errors="coerce").isna().sum())
    print("Demand parcels/day stats:", nta["Demand_parcels_per_day"].describe())


    # ---- Pairing logic ----
    # pairing="all": every NTA x every dispatch center
    # pairing="by_borough": NTA only with dispatch centers where Cluster_id == Borough
    if pairing == "by_borough":
        pairs = nta.merge(
            disp,
            left_on="Borough",
            right_on="Dispatch_cluster_id",
            how="inner",
            suffixes=("", "_disp"),
        )
    elif pairing == "all":
        nta["_tmp"] = 1
        disp["_tmp"] = 1
        pairs = nta.merge(disp, on="_tmp", how="inner").drop(columns=["_tmp"])
    else:
        raise ValueError("pairing must be 'by_borough' or 'all'")

    # ---- Distances ----
    pairs["euclid_km"] = pairs.apply(
        lambda r: haversine_km(float(r[LAT]), float(r[LON]), float(r[DISP_LAT]), float(r[DISP_LON])),
        axis=1,
    )
    pairs["Avg_route_length(km)"] = (pairs["euclid_km"] * network_factor).round(3)

    # ---- Scenarios (keep it simple + aligned to your engine fields) ----
    scenarios = [
        ("baseline", "none", 0),
        ("flood", "flood", 2),
        ("heat_wave", "heat_wave", 1),
        ("power_outage", "power_outage", 4),
    ]

    rows = []
    for _, r in pairs.iterrows():
        for scen_name, event_state, ev_down in scenarios:
            rows.append({
                "Scenario_id": f"{r[NTA_ID]}__{r['Dispatch_name']}__{scen_name}",
                "scenario": scen_name,
                "disruptive_event_state": event_state,
                "EV_downtime_hours": ev_down,

                # keys for joining/mapping
                "NTA2020": r[NTA_ID],
                "Borough": r["Borough"],
                "Dispatch_name": r["Dispatch_name"],
                "Dispatch_cluster_id": r["Dispatch_cluster_id"],

                # engine inputs (match your FIELD_MAP expectations)
                "Avg_route_length(km)": r["Avg_route_length(km)"],
                "Demand_parcels_per_day": int(r["Demand_parcels_per_day"]),
                "Speed_mult": float(r[SPEED]),

                # keep these for interpretation/QA
                "AADT_class": r.get(AADT_CLASS, None),
                "cent_lat": float(r[LAT]),
                "cent_lon": float(r[LON]),
                "dispatch_lat": float(r[DISP_LAT]),
                "dispatch_lon": float(r[DISP_LON]),
            })

    out = pd.DataFrame(rows)

    # Final check
    required_out = ["Scenario_id", "Avg_route_length(km)", "Demand_parcels_per_day", "Speed_mult", "EV_downtime_hours"]
    missing = [c for c in required_out if c not in out.columns]
    if missing:
        raise RuntimeError(f"Output missing required columns: {missing}")

    out.to_csv(out_csv, index=False)
    print(f"Saved: {out_csv}")
    print(f"Rows: {len(out):,}")
    print(f"Columns: {list(out.columns)}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--nta_csv", required=True)
    ap.add_argument("--dispatch_csv", required=True)
    ap.add_argument("--out_csv", required=True)
    ap.add_argument("--pairing", choices=["by_borough", "all"], default="all")
    ap.add_argument("--network_factor", type=float, default=1.30)  # simple network approximation
    ap.add_argument("--base_demand", type=float, default=1000)      # median NTA ~ 1000 parcels/day
    args = ap.parse_args()

    main(
        Path(args.nta_csv),
        Path(args.dispatch_csv),
        Path(args.out_csv),
        args.pairing,
        args.network_factor,
        args.base_demand,
    )
