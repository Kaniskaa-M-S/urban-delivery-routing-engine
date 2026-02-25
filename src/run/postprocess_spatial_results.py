# src/run/postprocess_spatial_results.py

import argparse
from pathlib import Path
import pandas as pd


def _mode_key(mode: str) -> str:
    m = str(mode).strip().lower()
    m = m.replace("-", " ").replace("/", " ").replace("__", "_")
    m = "_".join(m.split())
    # normalize common names to match your columns
    if m in {"cargo_bike", "cargo_bikes", "cargobike"}:
        return "cargo_bike"
    if m in {"e_van", "evan", "e_vans", "evan"}:
        return "e_van"
    if m in {"truck", "trucks"}:
        return "truck"
    return m


def _first_mode_to_fail(row, mode_cols):
    # order matters: you were seeing cargo_bike as first to fail in collapse
    order = ["cargo_bike_feas", "e_van_feas", "truck_feas"]
    for c in order:
        if c in mode_cols and (pd.isna(row.get(c)) or (row.get(c) is False)):
            return c.replace("_feas", "")
    return "none"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--infile",
        type=str,
        default=r"outputs_spatial\results_all_scenarios_feasible.csv",
        help="Input feasibility results CSV (LONG format output of run_batch_feasible).",
    )
    ap.add_argument(
        "--outdir",
        type=str,
        default=r"outputs_spatial",
        help="Directory to write spatial_results_*.csv",
    )
    args = ap.parse_args()

    infile = Path(args.infile)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    if not infile.exists():
        raise FileNotFoundError(f"Cannot find infile: {infile.resolve()}")

    df = pd.read_csv(infile)

    # ---- derive feasible_flag robustly ----
    if "feasible" in df.columns:
        # pandas may read TRUE/FALSE as bool OR strings depending on CSV
        if df["feasible"].dtype == bool:
            df["feasible_flag"] = df["feasible"]
        else:
            df["feasible_flag"] = df["feasible"].astype(str).str.lower().isin(["true", "1", "yes"])
    elif "infeasible_reason" in df.columns:
        df["feasible_flag"] = df["infeasible_reason"].astype(str).str.lower().eq("ok")
    else:
        raise KeyError(f"Need 'feasible' or 'infeasible_reason' in infile. Found: {list(df.columns)}")

    if "Scenario_id" not in df.columns or "mode" not in df.columns:
        raise KeyError(f"Need Scenario_id and mode columns. Found: {list(df.columns)}")

    df["mode_key"] = df["mode"].map(_mode_key)

    # ---- pivot to WIDE feasibility columns ----
    pivot = (
        df.pivot_table(index="Scenario_id", columns="mode_key", values="feasible_flag", aggfunc="max")
        .reset_index()
    )

    # rename to your expected names
    ren = {}
    for c in pivot.columns:
        if c == "Scenario_id":
            continue
        ren[c] = f"{c}_feas"
    pivot = pivot.rename(columns=ren)

    mode_cols = [c for c in pivot.columns if c.endswith("_feas")]

    # ---- bring scenario context columns (NTA, borough, dispatch, coords, etc.) ----
    # take first occurrence per Scenario_id
    context_cols = [
        c for c in df.columns
        if c not in {"mode", "mode_key", "feasible", "feasible_flag", "infeasible_reason",
                     "cost_per_km", "cost_total", "emissions_per_km", "emissions_total",
                     "speed_kmph", "time_hours", "effective_km", "demand_factor",
                     "extra_penalty_cost", "extra_penalty_emissions",
                     "max_service_radius_km", "max_parcels_per_day", "event_max_service_radius_km"}
    ]
    # keep Scenario_id plus any context columns that exist
    keep_context = [c for c in context_cols if c in df.columns]
    ctx = df[keep_context].drop_duplicates(subset=["Scenario_id"], keep="first")

    wide = ctx.merge(pivot, on="Scenario_id", how="left")

    # ---- derived summary fields ----
    # fill NaN as False for counting availability (if a mode never appeared)
    for c in mode_cols:
        wide[c] = wide[c].fillna(False)

    wide["modes_available"] = wide[mode_cols].sum(axis=1).astype(int)

    def _cat(n: int) -> str:
        if n == 3:
            return "3_all_modes"
        if n == 2:
            return "2_modes"
        if n == 1:
            return "1_mode"
        return "0_collapse"

    wide["mode_category"] = wide["modes_available"].map(_cat)
    wide["first_mode_to_fail"] = wide.apply(lambda r: _first_mode_to_fail(r, mode_cols), axis=1)

    # ---- baseline subset ----
    if "scenario" in wide.columns:
        baseline_mask = wide["scenario"].astype(str).str.lower().eq("baseline")
    elif "disruptive_event_state" in wide.columns:
        baseline_mask = wide["disruptive_event_state"].astype(str).str.lower().isin(["none", "baseline"])
    else:
        baseline_mask = pd.Series([False] * len(wide))

    wide_baseline = wide.loc[baseline_mask].copy()

    # ---- write outputs ----
    out_wide = outdir / "spatial_results_WIDE.csv"
    out_base_wide = outdir / "spatial_results_baseline_WIDE.csv"

    wide.to_csv(out_wide, index=False)
    wide_baseline.to_csv(out_base_wide, index=False)

    # optional: baseline LONG (raw rows for baseline)
    if "scenario" in df.columns:
        baseline_long_mask = df["scenario"].astype(str).str.lower().eq("baseline")
    elif "disruptive_event_state" in df.columns:
        baseline_long_mask = df["disruptive_event_state"].astype(str).str.lower().isin(["none", "baseline"])
    else:
        baseline_long_mask = pd.Series([False] * len(df))

    out_base_long = outdir / "spatial_results_baseline_LONG.csv"
    df.loc[baseline_long_mask].to_csv(out_base_long, index=False)

    print(f"Saved:\n  {out_wide}\n  {out_base_wide}\n  {out_base_long}")
    print(f"Rows wide: {len(wide):,} | Rows baseline wide: {len(wide_baseline):,} | Rows baseline long: {baseline_long_mask.sum():,}")


if __name__ == "__main__":
    main()
