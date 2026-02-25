# # src/run/run_sensitivity_setB.py


# from __future__ import annotations

# import argparse
# from itertools import product
# from pathlib import Path
# from typing import Any, Dict

# import pandas as pd

# from src.model.optimize_mix import optimize_mix_for_all_scenarios
# from src.model.optimize_mix import MixOptConfig

# # =========================
# # EDIT TO MATCH YOUR CSV
# # =========================
# FIELD_MAP = {
#     "avg_route_km": "Avg_route_length(km)",
#     "demand": "Demand_parcels_per_day",   # or "Demand_multiplier"
#     "speed_mult": "Speed_mult",
#     "ev_downtime_hr": "EV_downtime_hours",
# }
# DEMAND_IS_ABSOLUTE = True
# # =========================


# ROUTE_KM = [2, 4, 6, 8, 10, 12, 14, 16, 18, 20] 
# DEMAND_MULT = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]

# SPEED_MULT = [1.0, 0.9, 0.8, 0.7, 0.6, 0.55]
# EV_DOWNTIME_HR = [0, 1, 2, 3, 4, 6]


# def ensure_columns_exist(df: pd.DataFrame, required_cols: list[str]) -> None:
#     missing = [c for c in required_cols if c not in df.columns]
#     if missing:
#         raise ValueError(
#             f"Missing required columns in scenario CSV: {missing}\n"
#             f"CSV columns available: {list(df.columns)}\n"
#             f"Fix FIELD_MAP in src/run/run_sensitivity_setB.py to match your headers."
#         )


# def scenario_from_base(
#     base: Dict[str, Any],
#     avg_route_km: float | None = None,
#     demand_mult: float | None = None,
#     speed_mult: float | None = None,
#     ev_downtime_hr: float | None = None,
# ) -> Dict[str, Any]:
#     s = dict(base)

#     # Keep Scenario_id constant across sweep points (so metrics match correctly)
#     if "Scenario_id" in base:
#         s["Scenario_id"] = int(base["Scenario_id"])


#     if avg_route_km is not None:
#         s[FIELD_MAP["avg_route_km"]] = float(avg_route_km)

#     if demand_mult is not None:
#         if DEMAND_IS_ABSOLUTE:
#             base_parcels = float(base[FIELD_MAP["demand"]])
#             s[FIELD_MAP["demand"]] = float(base_parcels * demand_mult)
#             s["_demand_mult_used"] = float(demand_mult)
#         else:
#             s[FIELD_MAP["demand"]] = float(demand_mult)

#     if speed_mult is not None:
#         s[FIELD_MAP["speed_mult"]] = float(speed_mult)

#     if ev_downtime_hr is not None:
#         s[FIELD_MAP["ev_downtime_hr"]] = float(ev_downtime_hr)

#     return s


# def extract_single_row(result_obj: Any) -> Dict[str, Any]:
#     # handle (df_best, df_portfolio) returns
#     if isinstance(result_obj, tuple) and len(result_obj) >= 1:
#         result_obj = result_obj[0]

#     if isinstance(result_obj, pd.DataFrame):
#         if len(result_obj) == 0:
#             return {}
#         return result_obj.iloc[0].to_dict()

#     if isinstance(result_obj, dict):
#         return result_obj

#     try:
#         return dict(result_obj)
#     except Exception:
#         return {"_raw_result": str(result_obj)}


# def pick(row: Dict[str, Any], *keys: str, default: float = 0.0) -> float:
#     for k in keys:
#         if k in row and row[k] is not None:
#             try:
#                 return float(row[k])
#             except Exception:
#                 pass
#     return float(default)

# def standardize_output(row: Dict[str, Any]) -> Dict[str, Any]:
#     modes_available = row.get("modes_available", None)
#     if modes_available is None:
#         feasible = row.get("feasible_modes", None)
#         if isinstance(feasible, str):
#             sep = "|" if "|" in feasible else ","
#             modes_available = len([x for x in feasible.split(sep) if x.strip()])
#         elif isinstance(feasible, (list, tuple, set)):
#             modes_available = len(feasible)
#         else:
#             modes_available = 0

#     shares = {
#         "Cargo Bike": pick(row, "bike_share", "Cargo Bike_share", "share_bike", default=0.0),
#         "E-Van": pick(row, "ev_share", "E-Van_share", "share_ev", "share_evan", default=0.0),
#         "Truck": pick(row, "truck_share", "Truck_share", "share_truck", default=0.0),
#     }

#     total_cost = pick(row, "total_cost", "objective_cost", "objective", "min_cost_total", default=0.0)
#     total_emissions = pick(row, "total_emissions", "min_emissions_total", "emissions_total", default=0.0)
#     collapse_reason = row.get("collapse_reason", row.get("infeasible_reason", "none"))

#     return {
#         "modes_available": int(modes_available),
#         "shares": shares,
#         "total_cost": float(total_cost),
#         "total_emissions": float(total_emissions),
#         "collapse_reason": collapse_reason,
#     }

# def run_route_demand_sweep(
#     base_scenario: dict,
#     metrics_df: pd.DataFrame,
#     config: MixOptConfig
# ) -> pd.DataFrame:
#     results = []

#     base_speed = float(base_scenario.get(FIELD_MAP["speed_mult"], 1.0))
#     base_down = float(base_scenario.get(FIELD_MAP["ev_downtime_hr"], 0.0))

#     for route_km, dmult in product(ROUTE_KM, DEMAND_MULT):

#         scenario = scenario_from_base(
#             base_scenario,
#             avg_route_km=route_km,
#             demand_mult=dmult,
#         )

#         scenario_df = pd.DataFrame([scenario])
#         raw = optimize_mix_for_all_scenarios(metrics_df, scenario_df, config)

#         row = extract_single_row(raw)
#         out = standardize_output(row)

#         results.append({
#             "sweep": "route_x_demand",
#             "avg_route_km": route_km,
#             "demand_mult": dmult,
#             "speed_mult": base_speed,
#             "ev_downtime_hr": base_down,

#             "modes_available": out["modes_available"],
#             "collapse_flag": out["modes_available"] < 3,

#             "bike_share": out["shares"]["Cargo Bike"],
#             "ev_share": out["shares"]["E-Van"],
#             "truck_share": out["shares"]["Truck"],

#             "total_cost": out["total_cost"],
#             "total_emissions": out["total_emissions"],
#             "collapse_reason": out["collapse_reason"],
#         })

#     return pd.DataFrame(results)


# def run_congestion_downtime_sweep(
#     base_scenario: dict,
#     metrics_df: pd.DataFrame,
#     config: MixOptConfig
# ) -> pd.DataFrame:
#     results = []

#     base_route = float(base_scenario.get(FIELD_MAP["avg_route_km"], 0.0))
#     base_dmult = float(base_scenario.get("_demand_mult_used", 1.0))

#     for smult, down in product(SPEED_MULT, EV_DOWNTIME_HR):

#         scenario = scenario_from_base(
#             base_scenario,
#             speed_mult=smult,
#             ev_downtime_hr=down,
#         )

#         scenario_df = pd.DataFrame([scenario])
#         raw = optimize_mix_for_all_scenarios(metrics_df, scenario_df, config)

#         row = extract_single_row(raw)
#         out = standardize_output(row)

#         results.append({
#             "sweep": "congestion_x_ev_downtime",
#             "avg_route_km": base_route,
#             "demand_mult": base_dmult,
#             "speed_mult": smult,
#             "ev_downtime_hr": down,

#             "modes_available": out["modes_available"],
#             "collapse_flag": out["modes_available"] < 3,

#             "bike_share": out["shares"]["Cargo Bike"],
#             "ev_share": out["shares"]["E-Van"],
#             "truck_share": out["shares"]["Truck"],

#             "total_cost": out["total_cost"],
#             "total_emissions": out["total_emissions"],
#             "collapse_reason": out["collapse_reason"],
#         })

#     return pd.DataFrame(results)


# def main() -> None:
#     parser = argparse.ArgumentParser()
#     parser.add_argument("--scenario_csv", type=str, default="Cleaned Data/base_nyc_scenario.xlsx")
#     parser.add_argument("--row", type=int, default=0)
#     parser.add_argument("--outdir", type=str, default="outputs")
#     args = parser.parse_args()

#     outdir = Path(args.outdir)
#     outdir.mkdir(parents=True, exist_ok=True)

#     if args.scenario_csv.lower().endswith(".xlsx"):
#         df_base = pd.read_excel(args.scenario_csv, sheet_name=0)
#     else:
#         df_base = pd.read_csv (args.scenario_csv)

#     # >>> ADD THESE TWO LINES RIGHT HERE <<<
#     metrics_df = pd.read_csv("outputs/results_all_scenarios_feasible.csv")


#     config = MixOptConfig(
#         step=0.05,
#         w_cost=1.0,
#         w_emissions=0.0,
#         require_feasible_modes_only=False
#     )
#     # >>> STOP ADDING HERE <<<

#     required = [
#         FIELD_MAP["avg_route_km"],
#         FIELD_MAP["demand"],
#         FIELD_MAP["speed_mult"],
#         FIELD_MAP["ev_downtime_hr"],
#     ]
#     ensure_columns_exist(df_base, required)

#     base_scenario = df_base.iloc[int(args.row)].to_dict()

#     df1 = run_route_demand_sweep(base_scenario, metrics_df, config)
#     df2 = run_congestion_downtime_sweep(base_scenario, metrics_df, config)

#     out1 = outdir / "sensitivity_route_x_demand.csv"
#     out2 = outdir / "sensitivity_congestion_x_ev_downtime.csv"

#     df1.to_csv(out1, index=False)
#     df2.to_csv(out2, index=False)

#     print("Saved sensitivity outputs:")
#     print(f" - {out1}")
#     print(f" - {out2}")

#     print("\nQuick checks:")
#     print("Route×Demand runs:", len(df1), " collapse:", int(df1["collapse_flag"].sum()))
#     print("Congestion×Downtime runs:", len(df2), " collapse:", int(df2["collapse_flag"].sum()))


# if __name__ == "__main__":
#     main()

# src/run/run_sensitivity_setB.py

from __future__ import annotations

import argparse
from itertools import product
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from src.model.optimize_mix import optimize_mix_for_all_scenarios, MixOptConfig
from src.io.loaders import load_inputs
from src.model.mode_params import build_mode_params
from src.model.metrics import compute_metrics_for_scenario


# =========================
# EDIT TO MATCH YOUR EXCEL
# =========================
FIELD_MAP = {
    "avg_route_km": "Avg_route_length(km)",
    "demand": "Demand_parcels_per_day",
    "speed_mult": "Speed_mult",
    "ev_downtime_hr": "EV_downtime_hours",
}
DEMAND_IS_ABSOLUTE = True
# =========================

# Sensitivity grids
ROUTE_KM = [2, 4, 6, 8, 10, 12, 14, 16, 18, 20]
DEMAND_MULT = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]

SPEED_MULT = [1.0, 0.9, 0.8, 0.7, 0.6, 0.55]
EV_DOWNTIME_HR = [0, 1, 2, 3, 4, 6]


def ensure_columns_exist(df: pd.DataFrame, required_cols: list[str]) -> None:
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required columns in scenario sheet: {missing}\n"
            f"Columns available: {list(df.columns)}\n"
            f"Fix FIELD_MAP in src/run/run_sensitivity_setB.py to match your headers."
        )


def scenario_from_base(
    base: Dict[str, Any],
    avg_route_km: float | None = None,
    demand_mult: float | None = None,
    speed_mult: float | None = None,
    ev_downtime_hr: float | None = None,
) -> Dict[str, Any]:
    s = dict(base)

    # keep Scenario_id stable
    if "Scenario_id" in base and pd.notna(base["Scenario_id"]):
        s["Scenario_id"] = int(base["Scenario_id"])

    if avg_route_km is not None:
        s[FIELD_MAP["avg_route_km"]] = float(avg_route_km)

    if demand_mult is not None:
        if DEMAND_IS_ABSOLUTE:
            base_parcels = float(base[FIELD_MAP["demand"]])
            s[FIELD_MAP["demand"]] = float(base_parcels * demand_mult)
            s["_demand_mult_used"] = float(demand_mult)
        else:
            s[FIELD_MAP["demand"]] = float(demand_mult)

    if speed_mult is not None:
        s[FIELD_MAP["speed_mult"]] = float(speed_mult)

    if ev_downtime_hr is not None:
        s[FIELD_MAP["ev_downtime_hr"]] = float(ev_downtime_hr)

    return s


def extract_single_row(result_obj: Any) -> Dict[str, Any]:
    # handle (df_best, df_portfolio)
    if isinstance(result_obj, tuple) and len(result_obj) >= 1:
        result_obj = result_obj[0]

    if isinstance(result_obj, pd.DataFrame):
        if len(result_obj) == 0:
            return {}
        return result_obj.iloc[0].to_dict()

    if isinstance(result_obj, dict):
        return result_obj

    try:
        return dict(result_obj)
    except Exception:
        return {"_raw_result": str(result_obj)}


def pick(row: Dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for k in keys:
        if k in row and row[k] is not None:
            try:
                return float(row[k])
            except Exception:
                pass
    return float(default)


def standardize_output(row: Dict[str, Any]) -> Dict[str, Any]:
    # shares
    shares = {
        "Cargo Bike": pick(row, "bike_share", "Cargo Bike_share", "share_bike", default=0.0),
        "E-Van": pick(row, "ev_share", "E-Van_share", "share_ev", "share_evan", default=0.0),
        "Truck": pick(row, "truck_share", "Truck_share", "share_truck", default=0.0),
    }

    total_cost = pick(row, "total_cost", "objective_cost", "objective", "min_cost_total", default=float("nan"))
    total_emissions = pick(row, "total_emissions", "min_emissions_total", "emissions_total", default=float("nan"))
    collapse_reason = row.get("collapse_reason", row.get("infeasible_reason", "none"))

    return {
        "shares": shares,
        "total_cost": float(total_cost) if pd.notna(total_cost) else float("nan"),
        "total_emissions": float(total_emissions) if pd.notna(total_emissions) else float("nan"),
        "collapse_reason": collapse_reason,
    }


def recompute_metrics_one_scenario(
    scenario: Dict[str, Any],
    mode_params_df: pd.DataFrame,
    baseline_parcels: float,
) -> pd.DataFrame:
    """
    THIS is the key fix: recompute the per-mode feasibility/metrics for each sweep point.
    """
    m = compute_metrics_for_scenario(scenario, mode_params_df, baseline_parcels)

    if isinstance(m, list):
        m = pd.DataFrame(m)
    elif isinstance(m, dict):
        m = pd.DataFrame([m])

    # normalize feasible column to bool if needed
    if "feasible" in m.columns:
        m["feasible"] = m["feasible"].astype(str).str.lower().isin(["true", "1", "yes"])
    elif "feasible_flag" in m.columns:
        m["feasible"] = m["feasible_flag"].astype(str).str.lower().isin(["true", "1", "yes"])
    else:
        # if your metrics doesn't produce feasibility, that's a deeper bug
        raise KeyError(f"Metrics output missing 'feasible' column. Got: {list(m.columns)}")

    return m


def run_route_demand_sweep(
    base_scenario: dict,
    mode_params_df: pd.DataFrame,
    config: MixOptConfig,
    baseline_parcels: float,
) -> pd.DataFrame:
    results = []

    base_speed = float(base_scenario.get(FIELD_MAP["speed_mult"], 1.0))
    base_down = float(base_scenario.get(FIELD_MAP["ev_downtime_hr"], 0.0))

    for route_km, dmult in product(ROUTE_KM, DEMAND_MULT):
        scenario = scenario_from_base(base_scenario, avg_route_km=route_km, demand_mult=dmult)
        scenario_df = pd.DataFrame([scenario])

        metrics_df = recompute_metrics_one_scenario(scenario, mode_params_df, baseline_parcels)

        # modes_available + collapse are NOT inferred from optimizer output
        modes_available = int(metrics_df["feasible"].sum())
        collapse_flag = (modes_available == 0)

        raw = optimize_mix_for_all_scenarios(metrics_df, scenario_df, config)
        row = extract_single_row(raw)
        out = standardize_output(row)

        # If collapsed, shares should be 0 and totals should be NaN (not constant garbage)
        if collapse_flag:
            out["shares"]["Cargo Bike"] = 0.0
            out["shares"]["E-Van"] = 0.0
            out["shares"]["Truck"] = 0.0
            out["total_cost"] = float("nan")
            out["total_emissions"] = float("nan")
            out["collapse_reason"] = "no_feasible_modes"

        results.append({
            "sweep": "route_x_demand",
            "avg_route_km": route_km,
            "demand_mult": dmult,
            "speed_mult": base_speed,
            "ev_downtime_hr": base_down,

            "modes_available": modes_available,
            "collapse_flag": collapse_flag,

            "bike_share": out["shares"]["Cargo Bike"],
            "ev_share": out["shares"]["E-Van"],
            "truck_share": out["shares"]["Truck"],

            "total_cost": out["total_cost"],
            "total_emissions": out["total_emissions"],
            "collapse_reason": out["collapse_reason"],
        })

    return pd.DataFrame(results)


def run_congestion_downtime_sweep(
    base_scenario: dict,
    mode_params_df: pd.DataFrame,
    config: MixOptConfig,
    baseline_parcels: float,
) -> pd.DataFrame:
    results = []

    base_route = float(base_scenario.get(FIELD_MAP["avg_route_km"], 0.0))
    base_dmult = float(base_scenario.get("_demand_mult_used", 1.0))

    for smult, down in product(SPEED_MULT, EV_DOWNTIME_HR):
        scenario = scenario_from_base(base_scenario, speed_mult=smult, ev_downtime_hr=down)
        scenario_df = pd.DataFrame([scenario])

        metrics_df = recompute_metrics_one_scenario(scenario, mode_params_df, baseline_parcels)

        modes_available = int(metrics_df["feasible"].sum())
        collapse_flag = (modes_available == 0)

        raw = optimize_mix_for_all_scenarios(metrics_df, scenario_df, config)
        row = extract_single_row(raw)
        out = standardize_output(row)

        if collapse_flag:
            out["shares"]["Cargo Bike"] = 0.0
            out["shares"]["E-Van"] = 0.0
            out["shares"]["Truck"] = 0.0
            out["total_cost"] = float("nan")
            out["total_emissions"] = float("nan")
            out["collapse_reason"] = "no_feasible_modes"

        results.append({
            "sweep": "congestion_x_ev_downtime",
            "avg_route_km": base_route,
            "demand_mult": base_dmult,
            "speed_mult": smult,
            "ev_downtime_hr": down,

            "modes_available": modes_available,
            "collapse_flag": collapse_flag,

            "bike_share": out["shares"]["Cargo Bike"],
            "ev_share": out["shares"]["E-Van"],
            "truck_share": out["shares"]["Truck"],

            "total_cost": out["total_cost"],
            "total_emissions": out["total_emissions"],
            "collapse_reason": out["collapse_reason"],
        })

    return pd.DataFrame(results)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario_csv", type=str, default="Cleaned Data/base_nyc_scenario.xlsx")
    parser.add_argument("--row", type=int, default=0)
    parser.add_argument("--outdir", type=str, default="outputs")

    # NEW: load mode tables directly so sensitivity recomputes metrics correctly
    parser.add_argument("--mode_cost_xlsx", type=str, default="Cleaned Data/Mode_cost_parameters.xlsx")
    parser.add_argument("--mode_perf_xlsx", type=str, default="Cleaned Data/Mode_performance_parameters.xlsx")

    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # load scenario sheet
    if args.scenario_csv.lower().endswith(".xlsx"):
        df_base = pd.read_excel(args.scenario_csv, sheet_name=0)
    else:
        df_base = pd.read_csv(args.scenario_csv)

    required = [
        FIELD_MAP["avg_route_km"],
        FIELD_MAP["demand"],
        FIELD_MAP["speed_mult"],
        FIELD_MAP["ev_downtime_hr"],
    ]
    ensure_columns_exist(df_base, required)

    base_scenario = df_base.iloc[int(args.row)].to_dict()

    # load mode tables and build mode_params dataframe
    data = load_inputs(args.mode_cost_xlsx, args.mode_perf_xlsx, args.scenario_csv)
    mode_params_df = build_mode_params(data["mode_cost"], data["mode_perf"])

    # baseline parcels used by metrics engine
    baseline_parcels = float(base_scenario[FIELD_MAP["demand"]])

    config = MixOptConfig(
        step=0.05,
        w_cost=1.0,
        w_emissions=0.0,
        require_feasible_modes_only=False
    )

    df1 = run_route_demand_sweep(base_scenario, mode_params_df, config, baseline_parcels)
    df2 = run_congestion_downtime_sweep(base_scenario, mode_params_df, config, baseline_parcels)

    out1 = outdir / "sensitivity_route_x_demand.csv"
    out2 = outdir / "sensitivity_congestion_x_ev_downtime.csv"

    df1.to_csv(out1, index=False)
    df2.to_csv(out2, index=False)

    print("Saved sensitivity outputs:")
    print(f" - {out1}")
    print(f" - {out2}")

    print("\nQuick checks:")
    print("Route×Demand runs:", len(df1), " collapse:", int(df1["collapse_flag"].sum()))
    print("Congestion×Downtime runs:", len(df2), " collapse:", int(df2["collapse_flag"].sum()))


if __name__ == "__main__":
    main()
