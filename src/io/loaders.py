import pandas as pd
from pathlib import Path

def read_excel(path: Path, sheet_name=0) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    df = pd.read_excel(path, sheet_name=sheet_name)
    # Clean column names (common source of bugs)
    df.columns = [str(c).strip() for c in df.columns]
    return df

def load_inputs(mode_cost_xlsx: Path, mode_perf_xlsx: Path, scenario_xlsx: Path) -> dict:
    # Strip column names (handles hidden spaces)
    mode_perf = pd.read_excel(mode_perf_xlsx, sheet_name=0)
    mode_cost = pd.read_excel(mode_cost_xlsx, sheet_name=0)
    scenario  = pd.read_excel(scenario_xlsx, sheet_name=0)

    # Strip column names
    mode_perf.columns = mode_perf.columns.astype(str).str.strip()
    mode_cost.columns = mode_cost.columns.astype(str).str.strip()

    # Normalize column names
    mode_perf = mode_perf.rename(columns={
        "Modes": "mode",
        "Max Parcel /day": "max_parcels_per_day",
        "Max Service Radius  Km/ day": "max_service_radius_km",
        "Max Allowed Speed(kmh)": "speed_kmph",
        "Emission Factor (CO2/Km)": "emissions_per_km",
        "Congestion Sensitivity": "congestion_sensitivity",
    })
    print("\nMODE_PERF COLS EXACT:")
    for c in mode_perf.columns:
        print(repr(c))
        
    mode_cost = mode_cost.rename(columns={
        "Modes": "mode",
        "Cost_per_km": "cost_per_km",
    })

    # Sanity check
    if "mode" not in mode_perf.columns:
        raise KeyError(f"mode_perf missing 'mode'. Columns: {list(mode_perf.columns)}")
    if "mode" not in mode_cost.columns:
        raise KeyError(f"mode_cost missing 'mode'. Columns: {list(mode_cost.columns)}")

    mode_perf["mode"] = mode_perf["mode"].astype(str).str.strip()
    mode_cost["mode"] = mode_cost["mode"].astype(str).str.strip()

    return {
        "mode_cost": mode_cost,
        "mode_perf": mode_perf,
        "scenario": scenario,
    }