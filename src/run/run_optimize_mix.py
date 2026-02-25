import os
from pathlib import Path
import pandas as pd

from src.io.loaders import load_inputs
from src.model.mode_params import build_mode_params
from src.model.metrics import compute_metrics_for_scenario
from src.model.optimize_mix import optimize_mix_for_all_scenarios

MODE_COST_XLSX = r"C:\Users\ASUS\Desktop\Cornell\04) FALL 2025\02) Quantitative Foundations\Final project\06)VSCode\cleaned Data\Mode_cost_parameters.xlsx"
MODE_PERF_XLSX = r"C:\Users\ASUS\Desktop\Cornell\04) FALL 2025\02) Quantitative Foundations\Final project\06)VSCode\cleaned Data\Mode_performance_parameters.xlsx"
SCENARIO_XLSX  = r"C:\Users\ASUS\Desktop\Cornell\04) FALL 2025\02) Quantitative Foundations\Final project\06)VSCode\cleaned Data\Scenario Template.xlsx"

def main():
    # ✅ Convert strings -> Path objects (what your loader expects)
    data = load_inputs(Path(MODE_COST_XLSX), Path(MODE_PERF_XLSX), Path(SCENARIO_XLSX))

    mode_params = build_mode_params(data["mode_cost"], data["mode_perf"])
    scenarios = data["scenario"].copy()

    print("\n=== OPTIMIZER INPUT CHECK ===")
    print("Scenario shape:", scenarios.shape)
    print("Scenario IDs:", scenarios["Scenario_id"].tolist())

    baseline_parcels = 500.0
    metrics_df = pd.concat(
        [compute_metrics_for_scenario(s, mode_params, baseline_parcels) for _, s in scenarios.iterrows()],
        ignore_index=True
    )
    print("\n=== DEBUG: metrics_df columns ===")
    print(metrics_df.columns.tolist())
    print("shape:", metrics_df.shape)

    print(metrics_df.head(5))

    results_df, portfolio_df = optimize_mix_for_all_scenarios(metrics_df, scenarios)

    out_dir = os.path.join(os.getcwd(), "outputs")
    os.makedirs(out_dir, exist_ok=True)

    results_path = os.path.join(out_dir, "mix_opt_results.csv")
    results_df.to_csv(results_path, index=False)
    print(f"\nSaved results: {results_path}")

    if portfolio_df is not None and len(portfolio_df) > 0:
        portfolio_path = os.path.join(out_dir, "mix_opt_portfolio.csv")
        portfolio_df.to_csv(portfolio_path, index=False)
        print(f"Saved portfolio: {portfolio_path}")

    print("\nPreview:")
    print(results_df.head(20))

if __name__ == "__main__":
    main()
