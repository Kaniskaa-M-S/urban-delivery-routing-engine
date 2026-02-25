# src/model/optimize_mix.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple, List

import numpy as np
import pandas as pd


@dataclass
class MixOptConfig:
    step: float = 0.05            # grid step for shares (0.05 = 5%)
    w_cost: float = 1.0           # objective weight for cost
    w_emissions: float = 0.0      # objective weight for emissions (set >0 to include)
    require_feasible_modes_only: bool = False  # if your metrics table has "feasible_flag"


def _standardize_mode_name(s: str) -> str:
    s = str(s).strip().lower()
    if "cargo" in s and "bike" in s:
        return "Cargo Bike"
    if "e-van" in s or "evan" in s or ("van" in s and "e" in s):
        return "E-Van"
    if "truck" in s:
        return "Truck"
    return str(s)


def optimize_mix_for_all_scenarios(
    metrics_df: pd.DataFrame,
    scenario_df: pd.DataFrame,
    config: MixOptConfig = MixOptConfig(),
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    metrics_df: per-scenario per-mode table (e.g., outputs/results_all_scenarios.csv)
        Must include columns:
          - Scenario_id
          - mode
          - cost_total
          - emissions_total
        Optional:
          - feasible_flag (bool) if you want to disallow infeasible modes

    scenario_df: scenario table (from your scenario Excel)
        Should include:
          - Scenario_id
          - bike_share_cap (optional)
          - truck_share_floor (optional)

    Returns:
      (best_results_df, portfolio_df)
    """

    # --- Validate inputs ---
    required_metrics_cols = {"Scenario_id", "mode", "cost_total", "emissions_total"}
    missing = required_metrics_cols - set(metrics_df.columns)
    if missing:
        raise ValueError(f"metrics_df missing columns: {sorted(missing)}")

    if "Scenario_id" not in scenario_df.columns:
        raise ValueError("scenario_df must contain 'Scenario_id'")

    # Normalize mode names
    df = metrics_df.copy()
    df["mode"] = df["mode"].apply(_standardize_mode_name)

    # Keep only the 3 modes we optimize over
    df = df[df["mode"].isin(["Cargo Bike", "E-Van", "Truck"])].copy()
    ###ADDED- no filtering of scenarios here###
    if "feasible" in df.columns:
        df = df[df["feasible"] == True].copy()


    # Optional: enforce feasible-only modes if present
    if config.require_feasible_modes_only:
        if "feasible" not in df.columns:
            raise ValueError("require_feasible_modes_only=True but 'feasible' not found in metrics_df")
        df = df[df["feasible"] == True].copy()

    # Bring in scenario constraints
    scen = scenario_df.copy()
    # defaults
    if "bike_share_cap" not in scen.columns:
        scen["bike_share_cap"] = 1.0
    if "truck_share_floor" not in scen.columns:
        scen["truck_share_floor"] = 0.0

    scen["bike_share_cap"] = pd.to_numeric(scen["bike_share_cap"], errors="coerce").fillna(1.0)
    scen["truck_share_floor"] = pd.to_numeric(scen["truck_share_floor"], errors="coerce").fillna(0.0)

    # Create pivot tables for fast access
    pivot_cost = df.pivot(index="Scenario_id", columns="mode", values="cost_total")
    pivot_emis = df.pivot(index="Scenario_id", columns="mode", values="emissions_total")

    # Ensure every scenario has all 3 mode values

    # If not, that scenario will be skipped (and reported)
    # all_modes = ["Cargo Bike", "E-Van", "Truck"]
    # valid_scenarios = []
    # skipped = []
    # for sid in pivot_cost.index:
    #     if all(m in pivot_cost.columns for m in all_modes) and all(m in pivot_emis.columns for m in all_modes):
    #         row_ok = pivot_cost.loc[sid, all_modes].notna().all() and pivot_emis.loc[sid, all_modes].notna().all()
    #         if row_ok:
    #             valid_scenarios.append(sid)
    #         else:
    #             skipped.append(sid)
    #     else:
    #         skipped.append(sid)

    # Determine available modes per scenario (after infeasible rows removed)
    available_modes_by_scenario = (
        df.groupby("Scenario_id")["mode"]
        .apply(lambda x: sorted(x.unique().tolist()))
        .to_dict()
    )

    valid_scenarios = list(available_modes_by_scenario.keys())
    # skipped = []
    # if len(skipped) > 0:
    #     # not fatal, but you should know
    #     print(f"[optimize_mix] Skipping scenarios missing mode metrics: {sorted(set(skipped))}")

    # Pre-build grid
    step = float(config.step)
    grid = np.round(np.arange(0.0, 1.0 + 1e-9, step), 10)

    portfolio_rows: List[Dict] = []
    best_rows: List[Dict] = []

    scen_constraints = scen.set_index("Scenario_id")[["bike_share_cap", "truck_share_floor"]]

    for sid in valid_scenarios:
        # Constraints
        bike_cap = float(scen_constraints.loc[sid, "bike_share_cap"]) if sid in scen_constraints.index else 1.0
        truck_floor = float(scen_constraints.loc[sid, "truck_share_floor"]) if sid in scen_constraints.index else 0.0

        # Mode metrics
        # c_b = float(pivot_cost.loc[sid, "Cargo Bike"])
        # c_e = float(pivot_cost.loc[sid, "E-Van"])
        # c_t = float(pivot_cost.loc[sid, "Truck"])

        # e_b = float(pivot_emis.loc[sid, "Cargo Bike"])
        # e_e = float(pivot_emis.loc[sid, "E-Van"])
        # e_t = float(pivot_emis.loc[sid, "Truck"])
        modes = available_modes_by_scenario[sid]

        costs = {m: float(pivot_cost.loc[sid, m]) for m in modes}
        emis  = {m: float(pivot_emis.loc[sid, m]) for m in modes}


        best_obj = None
        best_choice = None

        # Enumerate feasible mixes
            # for x_b in grid:
            #     if x_b > bike_cap + 1e-12:
            #         continue
            #     for x_t in grid:
            #         if x_t + x_b > 1.0 + 1e-12:
            #             continue
            #         if x_t < truck_floor - 1e-12:
            #             continue
            #         x_e = 1.0 - x_b - x_t
            #         if x_e < -1e-12:
            #             continue

            #         total_cost = x_b * c_b + x_e * c_e + x_t * c_t
            #         total_emis = x_b * e_b + x_e * e_e + x_t * e_t
            #         obj = config.w_cost * total_cost + config.w_emissions * total_emis

            #         row = {
            #             "Scenario_id": sid,
            #             "x_bike": float(x_b),
            #             "x_evan": float(x_e),
            #             "x_truck": float(x_t),
            #             "bike_share_cap": bike_cap,
            #             "truck_share_floor": truck_floor,
            #             "total_cost": float(total_cost),
            #             "total_emissions": float(total_emis),
            #             "objective": float(obj),
            #         }
            #         portfolio_rows.append(row)

            #         if best_obj is None or obj < best_obj:
            #             best_obj = obj
            #             best_choice = row

        # Enumerate feasible mixes (supports 1, 2, or 3 available modes)
        modes = available_modes_by_scenario[sid]  # <-- created in step 2

        # helper to write shares consistently
        def _share_key(m: str) -> str:
            return "x_" + m.lower().replace("-", "").replace(" ", "")

        best_obj = None
        best_choice = None

        # -------------------------
        # CASE A) Only 1 mode exists
        # -------------------------
        if len(modes) == 1:
            m = modes[0]
            row = {
                "Scenario_id": sid,
                _share_key(m): 1.0,
                "bike_share_cap": bike_cap,
                "truck_share_floor": truck_floor,
                "total_cost": float(costs[m]),
                "total_emissions": float(emis[m]),
                "objective": float(config.w_cost * costs[m] + config.w_emissions * emis[m]),
            }
            portfolio_rows.append(row)
            best_choice = row

        # -------------------------
        # CASE B) Exactly 2 modes exist
        # -------------------------
        elif len(modes) == 2:
            m1, m2 = modes[0], modes[1]

            for x1 in grid:
                x2 = 1.0 - x1
                if x2 < -1e-12:
                    continue

                # enforce caps/floors ONLY if those modes exist
                # bike cap
                if m1 == "Cargo Bike" and x1 > bike_cap + 1e-12:
                    continue
                if m2 == "Cargo Bike" and x2 > bike_cap + 1e-12:
                    continue

                # truck floor
                if m1 == "Truck" and x1 < truck_floor - 1e-12:
                    continue
                if m2 == "Truck" and x2 < truck_floor - 1e-12:
                    continue

                total_cost = x1 * costs[m1] + x2 * costs[m2]
                total_emis = x1 * emis[m1] + x2 * emis[m2]
                obj = config.w_cost * total_cost + config.w_emissions * total_emis

                row = {
                    "Scenario_id": sid,
                    _share_key(m1): float(x1),
                    _share_key(m2): float(x2),
                    "bike_share_cap": bike_cap,
                    "truck_share_floor": truck_floor,
                    "total_cost": float(total_cost),
                    "total_emissions": float(total_emis),
                    "objective": float(obj),
                }
                portfolio_rows.append(row)

                if best_obj is None or obj < best_obj:
                    best_obj = obj
                    best_choice = row

        # -------------------------
        # CASE C) 3 modes exist (original logic, generalized)
        # -------------------------
        else:
            # enforce consistent ordering
            # (assumes your modes list contains these 3 names)
            m_b = "Cargo Bike"
            m_e = "E-Van"
            m_t = "Truck"

            for x_b in grid:
                if x_b > bike_cap + 1e-12:
                    continue
                for x_t in grid:
                    if x_t + x_b > 1.0 + 1e-12:
                        continue
                    if x_t < truck_floor - 1e-12:
                        continue

                    x_e = 1.0 - x_b - x_t
                    if x_e < -1e-12:
                        continue

                    total_cost = x_b * costs[m_b] + x_e * costs[m_e] + x_t * costs[m_t]
                    total_emis = x_b * emis[m_b] + x_e * emis[m_e] + x_t * emis[m_t]
                    obj = config.w_cost * total_cost + config.w_emissions * total_emis

                    row = {
                        "Scenario_id": sid,
                        "x_cargobike": float(x_b),
                        "x_evan": float(x_e),
                        "x_truck": float(x_t),
                        "bike_share_cap": bike_cap,
                        "truck_share_floor": truck_floor,
                        "total_cost": float(total_cost),
                        "total_emissions": float(total_emis),
                        "objective": float(obj),
                    }
                    portfolio_rows.append(row)

                    if best_obj is None or obj < best_obj:
                        best_obj = obj
                        best_choice = row

        if best_choice is None:
            best_rows.append({
                "Scenario_id": sid,
                "status": "NO_FEASIBLE_MIX",
                "bike_share_cap": bike_cap,
                "truck_share_floor": truck_floor,
            })
        else:
            best_out = best_choice.copy()
            best_out["status"] = "OK"
            best_rows.append(best_out)

    portfolio_df = pd.DataFrame(portfolio_rows)
    best_df = pd.DataFrame(best_rows)

    # Attach scenario context columns (borough, dispatch cluster, etc.) if present
    keep_context = [c for c in scenario_df.columns if c not in ["bike_share_cap", "truck_share_floor"]]
    scen_ctx = scenario_df[keep_context].drop_duplicates(subset=["Scenario_id"])
    best_df = best_df.merge(scen_ctx, on="Scenario_id", how="left")
    portfolio_df = portfolio_df.merge(scen_ctx, on="Scenario_id", how="left")

    return best_df, portfolio_df
