import pandas as pd

def _congestion_factor(level: str) -> float:
    lvl = str(level).strip().lower()
    if lvl == "low":
        return 0.2
    if lvl == "medium":
        return 0.5
    if lvl == "high":
        return 0.8
    return 0.5  # default

def weather_multipliers(Disruptive_event: str, mode: str):
    """
    Returns (speed_multiplier, cost_multiplier)
    Conservative defaults (not calibrated).
    """
    w = str(Disruptive_event).strip().lower()
    m = str(mode).strip().lower()

    # Defaults
    speed_mult = 1.0
    cost_mult = 1.0

    if w in ["", "nan", "none"]:
        return speed_mult, cost_mult

    if w == "normal":
        return 1.0, 1.0

    if w == "rain":
        if "cargo" in m or "bike" in m:
            return 0.85, 1.05
        return 0.95, 1.02

    if w == "snow":
        if "cargo" in m or "bike" in m:
            return 0.65, 1.15
        return 0.90, 1.05

    if w == "heatwave":
        if "cargo" in m or "bike" in m:
            return 0.90, 1.05
        return 0.97, 1.02

    return speed_mult, cost_mult

def check_mode_feasibility(s: pd.Series, m: pd.Series):
    """
    HARD constraints:
      - Avg_route_length(km) <= max_service_radius_km
      - Demand_parcels_per_day <= max_parcels_per_day

    SOFT penalties:
      - congestion reduces speed based on congestion_sensitivity
      - weather adjusts speed & cost via multipliers

    Returns:
      feasible(bool), reason(str), speed_multiplier(float), cost_multiplier(float)
    """
    dist_km = float(s["Avg_route_length(km)"])
    demand = float(s["Demand_parcels_per_day"])

    max_radius = float(m["max_service_radius_km"])
    max_parcels = float(m["max_parcels_per_day"])

    # Hard feasibility checks
    if pd.notna(max_radius) and dist_km > max_radius:
        return False, "distance_exceeds_max_service_radius", 0.0, 0.0

    if pd.notna(max_parcels) and demand > max_parcels:
        return False, "demand_exceeds_max_parcels_per_day", 0.0, 0.0

    # Soft penalties
    cong_factor = _congestion_factor(s.get("Congestion_level", "medium"))
    cong_sens = float(m.get("congestion_sensitivity", 0.0))

    # congestion reduces speed: speed * (1 - sens * factor)
    speed_mult_cong = max(0.3, 1.0 - cong_sens * cong_factor)

    # weather multipliers
    speed_mult_w, cost_mult_w = weather_multipliers(s.get("Disruptive_event", "normal"), m["mode"])

    speed_multiplier = speed_mult_cong * speed_mult_w
    cost_multiplier = cost_mult_w

    return True, "ok", speed_multiplier, cost_multiplier

# feasibility.py ---> ADDED BY K FOR ROUTING 

def check_mode_feasible_from_route(
    dist_km: float,
    demand_parcels: float,
    congestion_level: str,
    disruptive_event: str,
    mode_row: pd.Series,
):
    s = pd.Series({
        "Avg_route_length(km)": dist_km,
        "Demand_parcels_per_day": demand_parcels,
        "Congestion_level": congestion_level,
        "Disruptive_event": disruptive_event,
    })
    return check_mode_feasibility(s, mode_row)
