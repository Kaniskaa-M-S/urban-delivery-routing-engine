import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

OUTDIR = Path("outputs")
OUTDIR.mkdir(exist_ok=True)

def heatmap_from_grid(df, x, y, value, title, outfile):
    # pivot to grid
    grid = df.pivot_table(index=y, columns=x, values=value, aggfunc="mean")

    plt.figure()
    plt.imshow(grid.values, aspect="auto", origin="lower")
    plt.colorbar(label=value)
    plt.xticks(range(len(grid.columns)), [str(v) for v in grid.columns], rotation=45, ha="right")
    plt.yticks(range(len(grid.index)), [str(v) for v in grid.index])
    plt.xlabel(x)
    plt.ylabel(y)
    plt.title(title)
    plt.tight_layout()
    plt.savefig(outfile, dpi=200)
    plt.close()

def main():
    # 1) Route x Demand heatmap (modes_available)
    f1 = OUTDIR / "sensitivity_route_x_demand.csv"
    df1 = pd.read_csv(f1)

    # safety: ensure numeric
    for c in ["avg_route_km", "demand_mult", "modes_available"]:
        df1[c] = pd.to_numeric(df1[c], errors="coerce")

    heatmap_from_grid(
        df1,
        x="avg_route_km",
        y="demand_mult",
        value="modes_available",
        title="Modes available (Route length × Demand multiplier)",
        outfile=OUTDIR / "fig_heatmap_route_x_demand_modes_available.png",
    )

    # 2) Congestion x Downtime heatmap (modes_available)
    f2 = OUTDIR / "sensitivity_congestion_x_ev_downtime.csv"
    df2 = pd.read_csv(f2)

    for c in ["speed_mult", "ev_downtime_hr", "modes_available"]:
        df2[c] = pd.to_numeric(df2[c], errors="coerce")

    heatmap_from_grid(
        df2,
        x="ev_downtime_hr",
        y="speed_mult",
        value="modes_available",
        title="Modes available (Speed multiplier × EV downtime)",
        outfile=OUTDIR / "fig_heatmap_speed_x_downtime_modes_available.png",
    )

    # 3) Bike feasibility boundary scatter from base scenarios
    # Pull bike feasible from results_all_scenarios_feasible.csv
    f3 = OUTDIR / "results_all_scenarios_feasible.csv"
    df3 = pd.read_csv(f3)

    bike = df3[df3["mode"].astype(str).str.lower().str.contains("bike")].copy()
    bike["distance_km"] = pd.to_numeric(bike["distance_km"], errors="coerce")
    bike["demand_parcels_per_day"] = pd.to_numeric(bike["demand_parcels_per_day"], errors="coerce")
    bike["feasible_flag"] = bike["feasible"].astype(bool) if "feasible" in bike.columns else False

    plt.figure()
    plt.scatter(bike["distance_km"], bike["demand_parcels_per_day"])
    plt.xlabel("distance_km")
    plt.ylabel("demand_parcels_per_day")
    plt.title("Cargo bike feasibility samples (base scenarios)")
    plt.tight_layout()
    plt.savefig(OUTDIR / "fig_scatter_bike_feasibility_samples.png", dpi=200)
    plt.close()

    print("Saved figures into outputs/:")
    print("- fig_heatmap_route_x_demand_modes_available.png")
    print("- fig_heatmap_speed_x_downtime_modes_available.png")
    print("- fig_scatter_bike_feasibility_samples.png")

if __name__ == "__main__":
    main()
