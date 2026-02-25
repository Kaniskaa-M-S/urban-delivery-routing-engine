import pandas as pd

from src.model.feasibility import check_mode_feasibility
from src.model.disruptive_event import apply_disruptive_event


def compute_metrics_for_scenario(
    s: pd.Series,
    mode_params: pd.DataFrame,
    baseline_parcels: float
) -> pd.DataFrame:
    """
    For one scenario row `s`, compute per-mode metrics (cost, emissions, time),
    but only if feasible.

    What’s NEW vs your current version:
    - Calls apply_disruptive_event(...) to adjust:
        * speed (event + congestion/ops multipliers)
        * service radius (used for feasibility logic elsewhere, and traceability here)
        * EV downtime (adds to time)
        * hard bans (e.g., flood bans cargo bike)
        * extra penalties (crash risk, EJ burden, worker safety) added to totals
    - Outputs extra columns so you can debug WHY a mode shifts.
    """

    dist_km = float(s["Avg_route_length(km)"])
    parcels = float(s["Demand_parcels_per_day"])

    # Demand scaling: your current approach
    demand_factor = parcels / baseline_parcels if baseline_parcels else 1.0
    effective_km = dist_km * demand_factor

    rows = []

    for _, mr in mode_params.iterrows():
        # 1) Base feasibility (your existing logic)
        feasible, reason, speed_mult, cost_mult = check_mode_feasibility(s, mr)

        # 2) Disruptive event logic (hard bans + modifiers + penalties)
        event = apply_disruptive_event(
            scenario_row=s,  # pandas Series is dict-like
            mode=mr["mode"],
            base_speed_kmph=float(mr["speed_kmph"]),
            base_max_service_km=float(mr["max_service_radius_km"]),
            base_emissions_per_km=float(mr["emissions_per_km"]),
        )

        # Hard ban overrides everything
        if event["hard_infeasible"]:
            rows.append({
                "Scenario_id": s["Scenario_id"],
                "mode": mr["mode"],
                "feasible": False,
                "infeasible_reason": event["hard_reason"],

                "distance_km": dist_km,
                "demand_parcels_per_day": parcels,
                "demand_factor": demand_factor,
                "effective_km": effective_km,

                "disruptive_event_state": event["event_state"],
                "ev_downtime_hours": event["ev_downtime_hours"],
                "extra_penalty_cost": event["extra_penalty_cost"],
                "extra_penalty_emissions": event["extra_penalty_emissions"],

                # Keep traceability
                "base_speed_kmph": float(mr["speed_kmph"]),
                "event_speed_kmph": event["speed_kmph"],
                "base_max_service_radius_km": float(mr["max_service_radius_km"]),
                "event_max_service_radius_km": event["max_service_km"],
            })
            continue

        # If base feasibility already says infeasible, record and skip totals
        if not feasible:
            rows.append({
                "Scenario_id": s["Scenario_id"],
                "mode": mr["mode"],
                "feasible": False,
                "infeasible_reason": reason,

                "distance_km": dist_km,
                "demand_parcels_per_day": parcels,
                "demand_factor": demand_factor,
                "effective_km": effective_km,

                "disruptive_event_state": event["event_state"],
                "ev_downtime_hours": event["ev_downtime_hours"],
                "extra_penalty_cost": event["extra_penalty_cost"],
                "extra_penalty_emissions": event["extra_penalty_emissions"],

                "base_speed_kmph": float(mr["speed_kmph"]),
                "event_speed_kmph": event["speed_kmph"],
                "base_max_service_radius_km": float(mr["max_service_radius_km"]),
                "event_max_service_radius_km": event["max_service_km"],
            })
            continue

        # 3) Apply combined multipliers
        # Base feasibility gives speed_mult, cost_mult
        # Disruptive event returns already-adjusted speed_kmph and max_service_km,
        # so we use event speed directly (instead of multiplying twice).
        speed = float(event["speed_kmph"]) * float(speed_mult)

        cost_per_km = float(mr["cost_per_km"]) * float(cost_mult)
        emissions_per_km = float(mr["emissions_per_km"])

        # 4) Core totals (same as you had)
        cost_total = cost_per_km * effective_km
        emissions_total = emissions_per_km * effective_km
        time_hours = (effective_km / speed) if speed > 0 else None

        # 5) Add EV downtime to time (only matters for EV-like modes, but safe to add generally)
        if time_hours is not None:
            time_hours = time_hours + float(event["ev_downtime_hours"])

        # 6) Add penalties (crash/EJ/worker safety encoded as additive penalties)
        cost_total = cost_total + float(event["extra_penalty_cost"])
        emissions_total = emissions_total + float(event["extra_penalty_emissions"])

        rows.append({
            "Scenario_id": s["Scenario_id"],
            "mode": mr["mode"],
            "feasible": True,
            "infeasible_reason": "ok",

            "distance_km": dist_km,
            "demand_parcels_per_day": parcels,
            "demand_factor": demand_factor,
            "effective_km": effective_km,

            "cost_per_km": cost_per_km,
            "cost_total": cost_total,
            "emissions_per_km": emissions_per_km,
            "emissions_total": emissions_total,

            "speed_kmph": speed,
            "time_hours": time_hours,

            # keep both base + event-adjusted limits visible
            "max_service_radius_km": float(mr["max_service_radius_km"]),
            "max_parcels_per_day": float(mr["max_parcels_per_day"]),
            "event_max_service_radius_km": float(event["max_service_km"]),

            # disruptive event outputs
            "disruptive_event_state": event["event_state"],
            "ev_downtime_hours": float(event["ev_downtime_hours"]),
            "extra_penalty_cost": float(event["extra_penalty_cost"]),
            "extra_penalty_emissions": float(event["extra_penalty_emissions"]),
        })

    return pd.DataFrame(rows)
