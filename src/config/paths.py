from pathlib import Path
# Project root = the folder that contains "src", "outputs", "Cleaned Data"
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "cleaned Data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

# Your Excel input files
MODE_COST_XLSX = DATA_DIR / "Mode_cost_parameters.xlsx"
MODE_PERF_XLSX = DATA_DIR / "Mode_performance_parameters.xlsx"
UNCERTAIN_PERF_XLSX = DATA_DIR / "Uncertain_performance_parameters.xlsx"
SCENARIO_XLSX = DATA_DIR / "Scenario Template.xlsx"
