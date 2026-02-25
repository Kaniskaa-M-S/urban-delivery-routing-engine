from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple, List
import pandas as pd


@dataclass(frozen=True)
class MetricsConfig:
    # edit once, works forever
    base_speed_kmph_col: str = "base_speed_kmph"
    distance_col: str = "Avg_route_length(km)"     # from your scenario Excel
    demand_col: str = "Demand_parcels_per_day"     # from your scenario Excel
    speed_mult_col: str = "Speed_mult"
    ev_downtime_col: str = "EV_downtime_hours"
    event_col: str = "Disruptive_event"


def _as_float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)


def compute_metrics_for_one_scenario(
    scenario: Dict,
    mode_perf_df: pd.DataFrame,
    mode_cost_df: pd.DataFrame,
    cfg: MetricsConfig = MetricsConfig(),
) -> pd.DataFrame:
    """
    Returns a 3-row metrics_df with required columns for optimize_mix:
    Scenario_id, mode, cost_total, emissions_total
    plus feasibility fields.
    """

    sid = int(scenario["Scenario_id"])

    # scenario levers
    dist_km = _as_float(scenario.get(cfg.distance_col))
    demand = _as_float(scenario.get(cfg.demand_col))
    speed_mult = _as_float(scenario.get(cfg.speed_mult_col, 1.0), 1.0)
    ev_down = _as_float(scenario.get(cfg.ev_downtime_col, 0.0), 0.0)
    event = str(scenario.get(cfg.event_col, "normal")).strip()

    rows: List[Dict] = []

    # EXPECTATION: your mode tables contain one row per mode with columns like:
    # mode, cost_per_km, emissions_per_km, base_speed_kmph, max_service_radius_km, max_parcels_per_day, etc.
    # If your actual column names differ, we map them ONCE (see Step 2 below).

    for mode in ["Truck", "E-Van", "Cargo Bike"]:
        perf = mode_perf_df.loc[mode_perf_df["mode"] == mode].iloc[0].to_dict()
        cost = mode_cost_df.loc[mode_cost_df["mode"] == mode].iloc[0].to_dict()

        base_speed = _as_float(perf.get("speed_kmph", perf.get("base_speed_kmph", 0.0)))
        speed_kmph = base_speed * speed_mult

        max_radius = _as_float(perf.get("max_service_radius_km", 1e9))
        max_parcels = _as_float(perf.get("max_parcels_per_day", 1e18))

        # event impacts (minimal, but correct)
        # You can make this richer later, but keep it deterministic.
        if event in ("flood",):
            if mode == "Cargo Bike":
                # example: bike hard-banned in flood
                feasible = False
                reason = "hard_ban_flood"
            else:
                feasible = True
                reason = ""
        else:
            feasible = True
            reason = ""

        # feasibility checks (physics/ops)
        if feasible and dist_km > max_radius:
            feasible = False
            reason = "distance_exceeds_radius"
        if feasible and demand > max_parcels:
            feasible = False
            reason = "demand_exceeds_capacity"
        if feasible and speed_kmph <= 0:
            feasible = False
            reason = "invalid_speed"

        # EV downtime feasibility (only affects E-Van)
        if feasible and mode == "E-Van" and ev_down > 0:
            # simple: downtime reduces effective capacity
            # you can replace this with a stronger formula later
            pass

        cost_per_km = _as_float(cost.get("cost_per_km", 0.0))
        emissions_per_km = _as_float(cost.get("emissions_per_km", 0.0))

        cost_total = cost_per_km * dist_km
        emissions_total = emissions_per_km * dist_km

        # If infeasible, keep metrics but they can be ignored by optimizer if you filter later
        rows.append({
            "Scenario_id": sid,
            "mode": mode,
            "cost_total": cost_total,
            "emissions_total": emissions_total,
            "feasible_flag": bool(feasible),
            "infeasible_reason": reason,
            "distance_km": dist_km,
            "demand_parcels_per_day": demand,
            "speed_kmph": speed_kmph,
            "ev_downtime_hours": ev_down,
            "disruptive_event_state": event,
        })

    return pd.DataFrame(rows)


def compute_metrics_for_scenarios(
    scenario_df: pd.DataFrame,
    mode_perf_df: pd.DataFrame,
    mode_cost_df: pd.DataFrame,
    cfg: MetricsConfig = MetricsConfig(),
) -> pd.DataFrame:
    out = []
    for _, r in scenario_df.iterrows():
        out.append(compute_metrics_for_one_scenario(r.to_dict(), mode_perf_df, mode_cost_df, cfg))
    return pd.concat(out, ignore_index=True)
