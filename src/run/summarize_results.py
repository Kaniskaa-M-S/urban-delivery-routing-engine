import pandas as pd
from src.config.paths import OUTPUT_DIR

def main():
    in_path = OUTPUT_DIR / "results_all_scenarios.csv"
    df = pd.read_csv(in_path)

    # --- 1) Winner tables ---
    cheapest = df.loc[df.groupby("Scenario_id")["cost_total"].idxmin(), ["Scenario_id", "mode", "cost_total"]]
    cleanest = df.loc[df.groupby("Scenario_id")["emissions_total"].idxmin(), ["Scenario_id", "mode", "emissions_total"]]

    cheapest = cheapest.rename(columns={"mode": "cheapest_mode", "cost_total": "min_cost_total"})
    cleanest = cleanest.rename(columns={"mode": "cleanest_mode", "emissions_total": "min_emissions_total"})

    summary = pd.merge(cheapest, cleanest, on="Scenario_id", how="inner").sort_values("Scenario_id")

    # Carry scenario context (borough/cluster/etc.) from any row in scenario group
    context_cols = ["Borough", "Dispatch_cluster_id", "Distance_profile_type", "Congestion_level", "Policy_constraints_notes"]
    context = df.groupby("Scenario_id")[context_cols].first().reset_index()
    summary = pd.merge(context, summary, on="Scenario_id", how="left")

    out_summary = OUTPUT_DIR / "summary_by_scenario.csv"
    summary.to_csv(out_summary, index=False)

    # --- 2) Deltas vs Truck ---
    truck = df[df["mode"].str.lower().eq("truck")][["Scenario_id", "cost_total", "emissions_total"]].rename(
        columns={"cost_total": "truck_cost_total", "emissions_total": "truck_emissions_total"}
    )

    merged = pd.merge(df, truck, on="Scenario_id", how="left")

    merged["pct_cost_vs_truck"] = (merged["cost_total"] - merged["truck_cost_total"]) / merged["truck_cost_total"] * 100
    merged["pct_emissions_vs_truck"] = (merged["emissions_total"] - merged["truck_emissions_total"]) / merged["truck_emissions_total"] * 100

    out_delta = OUTPUT_DIR / "delta_vs_truck.csv"
    merged.to_csv(out_delta, index=False)

    # --- 3) Print quick insights (for you to paste in report draft) ---
    print("\nSaved:", out_summary)
    print("Saved:", out_delta)

    print("\n=== Quick insights ===")
    print("Cheapest mode counts:")
    print(summary["cheapest_mode"].value_counts())

    print("\nCleanest mode counts:")
    print(summary["cleanest_mode"].value_counts())

    print("\nPreview summary:")
    print(summary.head(10))

if __name__ == "__main__":
    main()
