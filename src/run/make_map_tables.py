from pathlib import Path
import pandas as pd


def pick_best_mode(long_df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns best mode by cost + best mode by emissions for each Scenario_id.
    Assumes long_df has: Scenario_id, mode, feasible, cost_total, emissions_total
    """
    df = long_df.copy()

    # Robust feasible flag
    if "feasible" in df.columns:
        feas = df["feasible"].astype(bool)
    else:
        feas = df.get("infeasible_reason", "").astype(str).str.lower().eq("ok")

    df = df[feas].copy()

    # Best by cost
    best_cost = (
        df.sort_values(["Scenario_id", "cost_total"], ascending=[True, True])
          .groupby("Scenario_id", as_index=False)
          .first()[["Scenario_id", "mode", "cost_total"]]
          .rename(columns={"mode": "best_mode_cost", "cost_total": "best_cost_total"})
    )

    # Best by emissions
    best_emis = (
        df.sort_values(["Scenario_id", "emissions_total"], ascending=[True, True])
          .groupby("Scenario_id", as_index=False)
          .first()[["Scenario_id", "mode", "emissions_total"]]
          .rename(columns={"mode": "best_mode_emissions", "emissions_total": "best_emissions_total"})
    )

    return best_cost.merge(best_emis, on="Scenario_id", how="outer")


def main():
    outdir = Path("outputs_spatial")

    baseline_wide = outdir / "spatial_results_baseline_WIDE.csv"
    baseline_long = outdir / "spatial_results_baseline_LONG.csv"
    all_wide      = outdir / "spatial_results_WIDE.csv"

    if not baseline_wide.exists():
        raise FileNotFoundError(f"Missing: {baseline_wide}")
    if not baseline_long.exists():
        raise FileNotFoundError(f"Missing: {baseline_long}")
    if not all_wide.exists():
        raise FileNotFoundError(f"Missing: {all_wide}")

    bw = pd.read_csv(baseline_wide)
    bl = pd.read_csv(baseline_long)
    aw = pd.read_csv(all_wide)
    # --- accept either column naming convention ---
    aw = aw.rename(columns={
        "cargo_bike_feas": "cargo_bike_feasible",
        "e_van_feas": "e_van_feasible",
        "truck_feas": "truck_feasible",
    })


    # ---------- BASELINE MAP TABLE (one row per NTA) ----------
    best_tbl = pick_best_mode(bl)

    bw2 = bw.merge(best_tbl, on="Scenario_id", how="left")

    # pick NEAREST dispatch per NTA (baseline)
    # (distance_km should exist in your wide; if it's named differently, fix here)
    if "distance_km" not in bw2.columns:
        # some earlier versions used "Avg_route_length(km)" or similar
        if "Avg_route_length(km)" in bw2.columns:
            bw2 = bw2.rename(columns={"Avg_route_length(km)": "distance_km"})
        else:
            raise KeyError(f"Can't find distance column in baseline wide. Columns: {list(bw2.columns)}")

    # ensure NTA join key exists
    if "NTA2020" not in bw2.columns:
        raise KeyError(f"NTA2020 missing in baseline wide. Columns: {list(bw2.columns)}")

    baseline_nta = (
        bw2.sort_values(["NTA2020", "distance_km"], ascending=[True, True])
           .groupby("NTA2020", as_index=False)
           .first()
    )

    # Keep only what you’ll actually map
    keep_cols = [
        "NTA2020", "Borough",
        "Dispatch_name", "Dispatch_cluster_id",
        "distance_km", "Demand_parcels_per_day", "Speed_mult", "AADT_class",
        "cargo_bike_feas", "e_van_feas", "truck_feas",
        "best_mode_cost", "best_cost_total",
        "best_mode_emissions", "best_emissions_total",
        "cent_lat", "cent_lon"
    ]
    keep_cols = [c for c in keep_cols if c in baseline_nta.columns]

    baseline_nta_out = baseline_nta[keep_cols].copy()
    baseline_nta_out.to_csv(outdir / "map_baseline_byNTA.csv", index=False)
    print("Saved:", outdir / "map_baseline_byNTA.csv")

    # ---------- ROBUSTNESS MAP TABLE (rate across scenarios, one row per NTA) ----------
    # Compute fraction of scenarios feasible for each NTA×Dispatch, then pick nearest dispatch for that NTA.
    needed = ["NTA2020", "Dispatch_name", "distance_km", "cargo_bike_feasible", "e_van_feasible", "truck_feasible"]
    for c in needed:
        if c not in aw.columns:
            raise KeyError(f"Missing {c} in spatial_results_WIDE.csv. Found: {list(aw.columns)}")

    rob = (
        aw.groupby(["NTA2020", "Dispatch_name"], as_index=False)
          .agg(
              distance_km=("distance_km", "min"),
              demand=("Demand_parcels_per_day", "median"),
              bike_feas_rate=("cargo_bike_feasible", "mean"),
              van_feas_rate=("e_van_feasible", "mean"),
              truck_feas_rate=("truck_feasible", "mean"),
          )
    )

    rob_pick = (
        rob.sort_values(["NTA2020", "distance_km"], ascending=[True, True])
           .groupby("NTA2020", as_index=False)
           .first()
    )

    rob_pick.to_csv(outdir / "map_robustness_byNTA.csv", index=False)
    print("Saved:", outdir / "map_robustness_byNTA.csv")


if __name__ == "__main__":
    main()
