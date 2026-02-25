# src/model/disruptive_event.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass
class EventEffects:
    # Multipliers applied to baseline mode parameters
    speed_mult: float = 1.0
    max_service_mult: float = 1.0

    # Extra downtime (primarily EV charging / network outages)
    ev_downtime_hours: float = 0.0

    # Hard bans by mode (e.g., flood -> no cargo bikes)
    hard_ban_modes: Tuple[str, ...] = ()

    # Soft penalties that express “externalities” (crash risk, EJ, worker safety)
    # These are added as extra costs (or emissions penalty proxy) so optimization can react.
    extra_cost: float = 0.0
    extra_emissions: float = 0.0


def _normalize_mode_name(mode: str) -> str:
    m = mode.strip().lower()
    if m in {"cargo bike", "cargobike", "bike"}:
        return "cargo bike"
    if m in {"e-van", "evan", "ev van", "electric van"}:
        return "e-van"
    if m in {"truck", "diesel truck"}:
        return "truck"
    return m


def _get_scenario_value(row: Dict, key: str, default=None):
    # row can be a pandas Series (dict-like)
    try:
        v = row.get(key, default)
    except Exception:
        v = row[key] if key in row else default
    return v


def get_event_library() -> Dict[str, EventEffects]:
    """
    Central place to define disruptive-event logic.
    Exclude wildfire smoke as requested.
    """
    return {
        "baseline": EventEffects(),

        # Rain -> congestion + safety delays. Truck hit hardest.
        "heavy_rain": EventEffects(
            speed_mult=0.85,          # general slowdown
            max_service_mult=0.95,    # slightly reduced achievable radius
            extra_cost=0.2,           # delay/ops friction proxy
        ),

        # Snow -> bikes constrained, EV charging slower, everyone slower.
        "snowstorm": EventEffects(
            speed_mult=0.75,
            max_service_mult=0.85,
            ev_downtime_hours=0.5,
            extra_cost=0.6,
        ),

        # Flood -> hard ban cargo bikes; EV may suffer if charging infra is down.
        "flood": EventEffects(
            speed_mult=0.70,
            max_service_mult=0.80,
            ev_downtime_hours=1.0,
            hard_ban_modes=("cargo bike",),
            extra_cost=1.2,
        ),

        # Heatwave -> battery derating, worker fatigue, more breaks; EV downtime rises.
        "heatwave": EventEffects(
            speed_mult=0.90,
            max_service_mult=0.90,
            ev_downtime_hours=0.7,
            extra_cost=0.5,
        ),

        # Power outage -> EV charging unreliable (can be near-hard constraint later).
        "power_outage": EventEffects(
            speed_mult=0.95,
            max_service_mult=0.95,
            ev_downtime_hours=2.0,
            extra_cost=1.0,
        ),

        # Crash surge near facilities -> truck risk + delays (ties to your screenshot).
        "major_crash_surge": EventEffects(
            speed_mult=0.90,
            extra_cost=0.8,
        ),

        # Curb access restrictions -> trucks get punished via dwell/parking; bikes favored.
        "curb_access_restrictions": EventEffects(
            speed_mult=0.92,
            extra_cost=0.7,
        ),

        # Labor shortage / safety enforcement -> slower ops, especially for bike transfer models.
        "labor_shortage": EventEffects(
            speed_mult=0.88,
            extra_cost=0.9,
        ),
    }


def apply_disruptive_event(
    scenario_row: Dict,
    mode: str,
    base_speed_kmph: float,
    base_max_service_km: float,
    base_emissions_per_km: float,
) -> Dict:
    """
    Returns a dict with adjusted parameters and penalties.

    We also inject your screenshot “critical features” as scenario-driven penalties:
    - Crash risk: penalize trucks more
    - EJ flag: penalize truck emissions more (proxy for EJ burden)
    - Worker safety sensitivity: penalize high manual/ops intensity
    """
    mode_n = _normalize_mode_name(mode)

    # Backward-compatible column name:
    event_state = (
        _get_scenario_value(scenario_row, "Disruptive_event_state", None)
        or _get_scenario_value(scenario_row, "Disruptive_event", "baseline")
        or "baseline"
    )
    event_state = str(event_state).strip().lower()

    lib = get_event_library()
    effects = lib.get(event_state, lib["baseline"])

    # Hard bans
    if mode_n in effects.hard_ban_modes:
        return {
            "event_state": event_state,
            "speed_kmph": base_speed_kmph,
            "max_service_km": base_max_service_km,
            "ev_downtime_hours": effects.ev_downtime_hours,
            "hard_infeasible": True,
            "hard_reason": f"{mode} banned under event={event_state}",
            "extra_penalty_cost": 0.0,
            "extra_penalty_emissions": 0.0,
        }

    # --- Speed & radius adjustments ---
    speed_kmph = base_speed_kmph * effects.speed_mult
    max_service_km = base_max_service_km * effects.max_service_mult

    # --- Screenshot-driven “critical features” implemented as penalties ---
    ej_flag = int(_get_scenario_value(scenario_row, "EJ_flag", 0) or 0)
    crash_risk = str(_get_scenario_value(scenario_row, "Crash_risk_level", "low")).strip().lower()
    worker_safety = str(_get_scenario_value(scenario_row, "Worker_safety_sensitivity", "low")).strip().lower()

    extra_cost = effects.extra_cost
    extra_emissions = effects.extra_emissions

    # 1) Traffic crashes near facilities (your screenshot)
    # Penalize trucks most, EVs a bit, bikes least.
    crash_mult = {"low": 0.0, "medium": 0.4, "high": 0.9}
    crash_pen = crash_mult.get(crash_risk, 0.0)
    if mode_n == "truck":
        extra_cost += 1.0 * crash_pen
    elif mode_n == "e-van":
        extra_cost += 0.5 * crash_pen
    else:  # cargo bike
        extra_cost += 0.2 * crash_pen

    # 2) Air quality & EJ (your screenshot)
    # In EJ zones, we apply an “emissions burden penalty” stronger for truck.
    if ej_flag == 1:
        if mode_n == "truck":
            extra_emissions += 0.5 * base_emissions_per_km  # proxy weight
        elif mode_n == "e-van":
            extra_emissions += 0.2 * base_emissions_per_km
        else:
            extra_emissions += 0.05 * base_emissions_per_km

    # 3) Worker safety (your screenshot)
    # Treat as an operational penalty: more sensitivity => higher “friction”
    safety_mult = {"low": 0.0, "medium": 0.3, "high": 0.7}
    safety_pen = safety_mult.get(worker_safety, 0.0)
    # Bikes can be more physically intensive (more exposure), trucks have injury severity.
    if mode_n == "cargo bike":
        extra_cost += 0.8 * safety_pen
    elif mode_n == "truck":
        extra_cost += 0.6 * safety_pen
    else:
        extra_cost += 0.4 * safety_pen

    return {
        "event_state": event_state,
        "speed_kmph": speed_kmph,
        "max_service_km": max_service_km,
        "ev_downtime_hours": effects.ev_downtime_hours,
        "hard_infeasible": False,
        "hard_reason": "",
        "extra_penalty_cost": float(extra_cost),
        "extra_penalty_emissions": float(extra_emissions),
    }
