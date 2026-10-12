"""Export the latest run of lab4-data-pipeline to a portable JSON file."""
from __future__ import annotations
import json
from pathlib import Path
import mlflow
from mlflow.tracking import MlflowClient

ROOT = Path(__file__).resolve().parents[1]
mlflow.set_tracking_uri("sqlite:///mlflow.db")
client = MlflowClient()
experiments = client.search_experiments(filter_string="name = 'lab4-data-pipeline'")
if not experiments:
    raise SystemExit("Experiment not found. Run `python -m src.pipeline` first.")
experiment = experiments[0]
runs = client.search_runs([experiment.experiment_id], order_by=["attributes.start_time DESC"], max_results=1)
if not runs:
    raise SystemExit("No MLflow runs found. Run `python -m src.pipeline` first.")
run = runs[0]
result = {
    "experiment_name": experiment.name,
    "run_id": run.info.run_id,
    "status": run.info.status,
    "start_time_ms": run.info.start_time,
    "params": run.data.params,
    "metrics": run.data.metrics,
    "tags": run.data.tags,
    "artifacts": [item.path for item in client.list_artifacts(run.info.run_id)],
}
out = ROOT / "docs" / "mlflow_run_export.json"
out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Exported latest MLflow run to {out}")
