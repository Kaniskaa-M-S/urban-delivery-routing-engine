# src/run/run_batch_feasible.py

from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd

from src.config.paths import MODE_COST_XLSX, MODE_PERF_XLSX
from src.io.loaders import load_inputs
from src.model.mode_params import build_mode_params
from src.model.metrics import compute_metrics_for_scenario


PASS_THROUGH_COLS = [
    "Scenario_id",
    "scenario",
    "disruptive_event_state",
    "EV_downtime_hours",
    "NTA2020",
    "Borough",
    "Dispatch_name",
    "Dispatch_cluster_id",
    "Avg_route_length(km)",
    "Demand_parcels_per_day",
    "Speed_mult",
    "AADT_class",
    "cent_lat",
    "cent_lon",
    "dispatch_lat",
    "dispatch_lon",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario_csv", required=True, help="Scenario CSV path")
    parser.add_argument("--outdir", default="outputs", help="Output directory")
    args = parser.parse_args()

    scenario_path = Path(args.scenario_csv)
    if not scenario_path.exists():
        raise FileNotFoundError(f"Scenario file not found: {scenario_path}")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # 1) read scenario CSV (NOT via load_inputs)
    scenario_df = pd.read_csv(scenario_path)

    # 2) read mode inputs from XLSX (keep your existing constants)
    mode_cost = pd.read_excel(MODE_COST_XLSX, sheet_name=0)
    mode_perf = pd.read_excel(MODE_PERF_XLSX, sheet_name=0)

    mode_params = build_mode_params(mode_cost, mode_perf)

    baseline_parcels = float(scenario_df.iloc[0]["Demand_parcels_per_day"])

    all_results = []
    for _, s in scenario_df.iterrows():
        r = compute_metrics_for_scenario(s, mode_params, baseline_parcels)

        # pass through scenario context columns
        for col in PASS_THROUGH_COLS:
            if col in s.index:
                r[col] = s[col]

        all_results.append(r)

    out = pd.concat(all_results, ignore_index=True)

    out_path = outdir / "results_all_scenarios_feasible.csv"
    out.to_csv(out_path, index=False)

    print("\nSaved:", out_path)
    print("\nCOLUMNS IN OUT:")
    print(list(out.columns))

    # quick sanity: should match your scenario demand range now
    if "demand_parcels_per_day" in out.columns:
        print("\nDemand stats in results (should be ~20–180 now):")
        print(out["demand_parcels_per_day"].describe())


if __name__ == "__main__":
    main()
