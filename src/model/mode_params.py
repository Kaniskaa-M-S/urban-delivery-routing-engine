import pandas as pd
import re

MI_TO_KM = 1.60934

def _norm(s: str) -> str:
    s = str(s).strip().lower()
    s = re.sub(r"\s+", " ", s)          # collapse spaces
    s = s.replace("\\", "/")            # unify slashes
    s = s.replace("per", "/")           # tolerate "per day" style
    s = s.replace(" / ", "/")           # tighten
    return s

def _find_col(df: pd.DataFrame, candidates: list[str]) -> str:
    """
    Find a column in df whose normalized name matches any normalized candidate.
    Raises a clear error if not found.
    """
    norm_map = {_norm(c): c for c in df.columns}
    for cand in candidates:
        nc = _norm(cand)
        if nc in norm_map:
            return norm_map[nc]

    # fallback: contains-based search
    for key, orig in norm_map.items():
        if "service radius" in key and ("km" in key) and ("day" in key or "/day" in key):
            return orig

    raise KeyError(
        "Could not find a 'Max Service Radius' column. "
        f"Tried candidates={candidates}. "
        f"Available columns={list(df.columns)}"
    )

# def build_mode_params(mode_cost: pd.DataFrame, mode_perf: pd.DataFrame) -> pd.DataFrame:
#     mc = mode_cost.copy()
#     if "cost_per_km" in mc.columns and "Cost_per_km" in mc.columns:
#         mc = mc.drop(columns=["cost_per_km"])
#     mp = mode_perf.copy()

#     # --- COST: compute cost_per_km from component cost columns (per mile) ---
#     # --- COST: read cost_per_km directly from Excel (no hard coding) ---

#     # normalize mode column early
#     if "mode" not in mc.columns:
#         if "Modes" in mc.columns:
#             mc = mc.rename(columns={"Modes": "mode"})
#         else:
#             raise KeyError(f"mode_cost missing mode column. cols={list(mc.columns)}")

#     # find cost_per_km column (robust to naming)
#     def _find_any(df, candidates):
#         for c in candidates:
#             if c in df.columns:
#                 return c
#         return None

#     # Prefer the explicit Excel column (case-sensitive) if present
#     if "Cost_per_km" in mc.columns:
#         col_costpkm = "Cost_per_km"
#     elif "cost_per_km" in mc.columns:
#         col_costpkm = "cost_per_km"
#     else:
#         col_costpkm = _find_any(
#             mc,
#             ["Cost per km", "Cost_per_km ($/km)"]
#         )


#     if col_costpkm is None:
#         raise KeyError(
#             "Mode_cost_parameters.xlsx must contain a 'Cost_per_km' column. "
#             f"Found columns: {list(mc.columns)}"
#         )

#     mc["cost_per_km"] = pd.to_numeric(mc[col_costpkm], errors="coerce")

#     print("\nDEBUG mode_cost columns:", list(mc.columns))
#     print("DEBUG cost_per_km head:\n", mc[["mode", col_costpkm]].head(10))
#     print("DEBUG dtypes:\n", mc.dtypes)

#     if mc["cost_per_km"].isna().any():
#         bad = mc.loc[mc["cost_per_km"].isna(), "mode"].tolist()
#         raise ValueError(f"Invalid cost_per_km for modes: {bad}")


#     # --- PERF: locate columns robustly ---
#     def num(col):
#         return pd.to_numeric(mp[col], errors="coerce")

#     # --- PERF: exact column names from your Excel ---
#     col_speed   = "Max Allowed Speed(kmh)"
#     col_emis    = "Emission Factor (CO2/Km)"
#     col_maxpar  = "Max Parcel /day"
#     col_radius  = "Max Service Radius  Km/ day"
#     col_cong    = "Congestion Sensitivity"  # optional but you have it
#     # --- FORCE Max Service Radius (never pick Min by accident) ---
#     # Your Excel header has double spaces: "Max Service Radius  Km/ day"
#     if "max_service_radius_km" in mp.columns:
#         col_radius = "max_service_radius_km"
#     else:
#         # Otherwise, try to locate the raw Excel column
#         if "Max Service Radius  Km/ day" in mp.columns:
#             col_radius = "Max Service Radius  Km/ day"
#         elif "Max Service Radius Km/ day" in mp.columns:
#             col_radius = "Max Service Radius Km/ day"
#         else:
#             candidates = [c for c in mp.columns
#                         if ("max" in str(c).lower() and "service radius" in str(c).lower())]
#             if not candidates:
#                 raise KeyError(
#                     f"Could not find MAX service radius column. Available: {list(mp.columns)}"
#                 )
#             col_radius = candidates[0]


#     mp["speed_kmph"] = pd.to_numeric(mp[col_speed], errors="coerce")
#     mp["emissions_per_km"] = pd.to_numeric(mp[col_emis], errors="coerce")
#     mp["max_parcels_per_day"] = pd.to_numeric(mp[col_maxpar], errors="coerce")
#     mp["max_service_radius_km"] = pd.to_numeric(mp[col_radius], errors="coerce")
#     mp["congestion_sensitivity"] = pd.to_numeric(mp[col_cong], errors="coerce").fillna(0.0)

#     # congestion sensitivity optional
#     try:
#         col_cong = _find_col(mp, ["Congestion Sensitivity", "Congestion_sensitivity"])
#         mp["congestion_sensitivity"] = num(col_cong).fillna(0.0)
#     except KeyError:
#         mp["congestion_sensitivity"] = 0.0

#     # join cost + perf
#     # Accept either raw Excel column name ('mode') or normalized ('mode')
#     def _get_mode_col(df):
#         if "mode" in df.columns:
#             return "mode"
#         if "Modes" in df.columns:
#             return "Modes"
#         return None

#     mode_col_cost = _get_mode_col(mode_cost)
#     mode_col_perf = _get_mode_col(mode_perf)

#     if mode_col_cost is None or mode_col_perf is None:
#         raise KeyError(
#             f"mode_cost and mode_perf must have a mode column ('mode' or 'mode'). "
#             f"mode_cost cols: {list(mode_cost.columns)} | mode_perf cols: {list(mode_perf.columns)}"
#         )

#     # Normalize both to 'mode' so the rest of the function is stable
#     if mode_col_cost != "mode":
#         mode_cost = mode_cost.rename(columns={mode_col_cost: "mode"})
#     if mode_col_perf != "mode":
#         mode_perf = mode_perf.rename(columns={mode_col_perf: "mode"})


#     out = pd.merge(
#         mc[["mode", "cost_per_km"]],
#         mp[["mode", "speed_kmph", "emissions_per_km", "max_service_radius_km", "max_parcels_per_day", "congestion_sensitivity"]],
#         on="mode",
#         how="inner"
#     )
#     print("\nSANITY CHECK mode params:")
#     print(out[["mode","max_parcels_per_day","max_service_radius_km","speed_kmph","emissions_per_km","cost_per_km"]])

#     out = out.rename(columns={"mode": "mode"})
#     return out[
#         ["mode", "cost_per_km", "emissions_per_km", "speed_kmph",
#          "max_service_radius_km", "max_parcels_per_day", "congestion_sensitivity"]
#     ]

import pandas as pd

def build_mode_params(mode_cost: pd.DataFrame, mode_perf: pd.DataFrame) -> pd.DataFrame:
   
    mc = mode_cost.copy()

    # strip whitespace, standardize
    mc.columns = [str(c).strip() for c in mc.columns]

    # rename common variants
    rename_cost = {
        "Modes": "mode",
        "Mode": "mode",
        "MODE": "mode",
        "Cost_per_km": "cost_per_km",
        "Cost per km": "cost_per_km",
        "cost_per_km": "cost_per_km",
    }
    mc = mc.rename(columns={k: v for k, v in rename_cost.items() if k in mc.columns})

    # ensure mode is string-clean
    if "mode" in mc.columns:
        mc["mode"] = mc["mode"].astype(str).str.strip()

    mp = mode_perf.copy()
    # --- normalize mode_perf column names to expected schema ---
    mp.columns = [str(c).strip() for c in mp.columns]

    rename_perf = {
        "Modes": "mode",
        "Mode": "mode",
        "mode": "mode",

        # capacity
        "Max Parcel /day": "max_parcels_per_day",
        "Max Parcel/day": "max_parcels_per_day",
        "max_parcels_per_day": "max_parcels_per_day",

        # radius
        "Max Service Radius  Km/ day": "max_service_radius_km",
        "Max Service Radius Km/ day": "max_service_radius_km",
        "Max Service Radius (Km/ day)": "max_service_radius_km",
        "max_service_radius_km": "max_service_radius_km",

        # speed
        "Max Allowed Speed(kmh)": "speed_kmph",
        "Max Allowed Speed (kmh)": "speed_kmph",
        "Max Allowed Speed(km/h)": "speed_kmph",
        "speed_kmph": "speed_kmph",

        # emissions
        "Emission Factor (CO2/Km)": "emissions_per_km",
        "Emission Factor (CO2/km)": "emissions_per_km",
        "emissions_per_km": "emissions_per_km",

        # congestion
        "Congestion Sensitivity": "congestion_sensitivity",
        "congestion_sensitivity": "congestion_sensitivity",
    }

    mp = mp.rename(columns={k: v for k, v in rename_perf.items() if k in mp.columns})

    # clean mode values
    if "mode" in mp.columns:
        mp["mode"] = mp["mode"].astype(str).str.strip()

    # force numerics (prevents silent string math)
    for c in ["max_parcels_per_day", "max_service_radius_km", "speed_kmph", "emissions_per_km", "congestion_sensitivity"]:
        if c in mp.columns:
            mp[c] = pd.to_numeric(mp[c], errors="coerce")



    # ---- REQUIRED normalized columns ----
    req_cost = {"mode", "cost_per_km"}
    req_perf = {"mode", "speed_kmph", "emissions_per_km", "max_service_radius_km", "max_parcels_per_day"}

    missing_cost = req_cost - set(mc.columns)
    missing_perf = req_perf - set(mp.columns)

    if missing_cost:
        raise KeyError(f"mode_cost missing columns: {sorted(missing_cost)}. Found: {list(mc.columns)}")
    if missing_perf:
        raise KeyError(f"mode_perf missing columns: {sorted(missing_perf)}. Found: {list(mp.columns)}")

    # ---- Clean + numeric ----
    mc["mode"] = mc["mode"].astype(str).str.strip()
    mp["mode"] = mp["mode"].astype(str).str.strip()

    for c in ["cost_per_km"]:
        mc[c] = pd.to_numeric(mc[c], errors="coerce")
    for c in ["speed_kmph", "emissions_per_km", "max_service_radius_km", "max_parcels_per_day"]:
        mp[c] = pd.to_numeric(mp[c], errors="coerce")

    # optional congestion sensitivity
    if "congestion_sensitivity" not in mp.columns:
        # if you kept the raw name
        if "Congestion Sensitivity" in mp.columns:
            mp["congestion_sensitivity"] = pd.to_numeric(mp["Congestion Sensitivity"], errors="coerce").fillna(0.0)
        else:
            mp["congestion_sensitivity"] = 0.0
    else:
        mp["congestion_sensitivity"] = pd.to_numeric(mp["congestion_sensitivity"], errors="coerce").fillna(0.0)

    out = pd.merge(
        mc[["mode", "cost_per_km"]],
        mp[["mode", "speed_kmph", "emissions_per_km", "max_service_radius_km", "max_parcels_per_day", "congestion_sensitivity"]],
        on="mode",
        how="inner"
    )
    # Add realistic delivery friction (defaults; replace with Excel columns later)
    defaults = {
        "truck": {"curb_penalty_min": 8, "service_time_min_per_parcel": 0.15},
        "e-van": {"curb_penalty_min": 4, "service_time_min_per_parcel": 0.12},
        "cargo bike": {"curb_penalty_min": 1, "service_time_min_per_parcel": 0.18},
        "cargo_bike": {"curb_penalty_min": 1, "service_time_min_per_parcel": 0.18},
    }

    def k(m): return str(m).strip().lower()
    out["curb_penalty_min"] = out["mode"].apply(lambda m: defaults.get(k(m), {}).get("curb_penalty_min", 5))
    out["service_time_min_per_parcel"] = out["mode"].apply(lambda m: defaults.get(k(m), {}).get("service_time_min_per_parcel", 0.15))

    # sanity
    bad = out[out["cost_per_km"].isna() | (out["cost_per_km"] <= 0)]
    if len(bad) > 0:
        raise ValueError(f"Invalid cost_per_km for modes: {bad['mode'].tolist()}")

    return out
