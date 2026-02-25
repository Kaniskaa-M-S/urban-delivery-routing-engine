from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
import numpy as np

def main(in_csv: Path, out_csv: Path, baseline_value: str, rule: str):
    df = pd.read_csv(in_csv)

    # ---- baseline filter ----
    # change this if your baseline column is named differently
    if "scenario" in df.columns:
        base = df[df["scenario"].astype(str) == baseline_value].copy()
    elif "disruptive_event_state" in df.columns:
        base = df[df["disruptive_event_state"].astype(str) == baseline_value].copy()
    else:
        raise KeyError("Cannot find scenario/disruptive_event_state column to filter baseline.")

    # ---- required columns ----
    required = ["NTA2020"]
    for c in required:
        if c not in base.columns:
            raise KeyError(f"Missing required column: {c}")

    # Guess distance column name
    dist_col = None
    for c in ["Avg_route_length(km)", "avg_route_km", "distance_km", "est_network_km"]:
        if c in base.columns:
            dist_col = c
            break
    if dist_col is None:
        raise KeyError("Could not find a distance column (Avg_route_length(km) / avg_route_km / distance_km).")

    # Guess feasibility columns (adjust if yours differ)
    bike_col = next((c for c in ["cargo_bike_feas", "bike_feasible", "Cargo Bike_feasible"] if c in base.columns), None)
    van_col  = next((c for c in ["e_van_feas", "van_feasible", "EV_feasible"] if c in base.columns), None)
    truck_col= next((c for c in ["truck_feas", "truck_feasible"] if c in base.columns), None)

    if bike_col is None or van_col is None or truck_col is None:
        raise KeyError("Could not find feasibility columns for bike/van/truck in your file.")

    # Ensure booleans as 0/1
    for c in [bike_col, van_col, truck_col]:
        base[c] = base[c].astype(str).str.lower().map({"true":1, "false":0}).fillna(pd.to_numeric(base[c], errors="coerce")).fillna(0).astype(int)

    base["modes_available"] = base[bike_col] + base[van_col] + base[truck_col]

    # ---- choose 1 row per NTA ----
    if rule == "closest":
        idx = base.groupby("NTA2020")[dist_col].idxmin()
        pick = base.loc[idx].copy()

    elif rule == "best":
        # best = max modes_available, tie-breaker min distance
        base["_neg_modes"] = -base["modes_available"]
        base["_dist"] = pd.to_numeric(base[dist_col], errors="coerce").fillna(np.inf)
        base = base.sort_values(["NTA2020", "_neg_modes", "_dist"])
        pick = base.groupby("NTA2020").head(1).copy()
        pick = pick.drop(columns=["_neg_modes", "_dist"], errors="ignore")

    else:
        raise ValueError("rule must be 'closest' or 'best'")

    # ---- output keepers ----
    keep = ["NTA2020", dist_col, "modes_available", bike_col, van_col, truck_col]
    for c in ["Dispatch_name", "dispatch_name", "Dispatch_cluster_id", "Borough", "AADT_class", "speed_mult", "Demand_parcels_per_day"]:
        if c in pick.columns:
            keep.append(c)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    pick[keep].to_csv(out_csv, index=False)
    print(f"Saved: {out_csv} ({len(pick)} rows) using rule={rule}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--in_csv", required=True, help="Your WIDE results csv (NTA×dispatch×scenario)")
    ap.add_argument("--out_csv", required=True, help="Output one-row-per-NTA mapping table")
    ap.add_argument("--baseline_value", default="baseline", help="Value used for baseline in scenario/disruptive_event_state")
    ap.add_argument("--rule", choices=["closest", "best"], default="closest")
    args = ap.parse_args()

    main(Path(args.in_csv), Path(args.out_csv), args.baseline_value, args.rule)
