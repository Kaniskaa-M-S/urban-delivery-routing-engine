from src.config.paths import MODE_COST_XLSX, MODE_PERF_XLSX, SCENARIO_XLSX, OUTPUT_DIR
from src.io.loaders import load_inputs
from src.model.mode_params import build_mode_params
from src.model.metrics import compute_metrics_for_scenario

def main():
    data = load_inputs(MODE_COST_XLSX, MODE_PERF_XLSX, SCENARIO_XLSX)

    mode_params = build_mode_params(data["mode_cost"], data["mode_perf"])
    scenario_df = data["scenario"]

    # baseline parcels = Scenario 1 parcels/day
    baseline_parcels = float(scenario_df.iloc[0]["Demand_parcels_per_day"])

    # run scenario 1 for now
    s = scenario_df.iloc[0]
    results = compute_metrics_for_scenario(s, mode_params, baseline_parcels)

    print("\n=== MODE PARAMS (clean) ===")
    print(mode_params)

    print("\n=== RESULTS (Scenario 1) ===")
    print(results)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"results_s{int(s['Scenario_id'])}.csv"
    results.to_csv(out_path, index=False)
    print(f"\nSaved: {out_path}")

if __name__ == "__main__":
    main()
