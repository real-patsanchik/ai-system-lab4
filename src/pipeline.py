"""Reproducible telemetry preparation pipeline: validate -> clean -> time split -> fit/transform."""
from __future__ import annotations
import json, os, hashlib
import yaml
from pathlib import Path
import joblib
import mlflow
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from src.contracts import validate_raw_telemetry

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/telemetry.csv"
OUT = ROOT / "data/processed"
ART = ROOT / "artifacts"
PARAMS = ROOT / "params.yaml"

def _read_params() -> dict:
    with PARAMS.open("r", encoding="utf-8") as stream:
        params = yaml.safe_load(stream) or {}
    defaults = {"train_share": 0.8, "random_seed": 42, "split_strategy": "time_ordered"}
    defaults.update(params)
    return defaults

def build_preprocessor() -> ColumnTransformer:
    numeric = ["temperature", "vibration", "pressure"]
    categorical = ["operating_mode"]
    return ColumnTransformer(transformers=[
        ("num", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]), numeric),
        ("cat", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]), categorical),
    ])

def run_pipeline(raw_path: Path = RAW, out_dir: Path = OUT, artifact_dir: Path = ART, track_mlflow: bool = True) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True); artifact_dir.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(raw_path, parse_dates=["timestamp"])
    validated = validate_raw_telemetry(raw)
    # Count and remove full-row duplicates after validation. Stable sort enables temporal split.
    duplicate_rows = int(validated.duplicated().sum())
    clean = validated.drop_duplicates().sort_values("timestamp", kind="stable").reset_index(drop=True)
    if len(clean) < 10:
        raise ValueError(f"At least 10 unique valid rows are required; got {len(clean)}")
    params = _read_params(); split_at = int(len(clean) * params["train_share"])
    if split_at <= 0 or split_at >= len(clean):
        raise ValueError("Time split must produce non-empty train and test sets")
    train_df, test_df = clean.iloc[:split_at].copy(), clean.iloc[split_at:].copy()
    feature_cols = ["temperature", "vibration", "pressure", "operating_mode"]
    preprocessor = build_preprocessor()
    # Critical leakage prevention: fit only on train; test sees transform only.
    x_train = preprocessor.fit_transform(train_df[feature_cols])
    x_test = preprocessor.transform(test_df[feature_cols])
    feature_names = preprocessor.get_feature_names_out().tolist()
    train_out = pd.DataFrame(x_train, columns=feature_names); test_out = pd.DataFrame(x_test, columns=feature_names)
    train_out["is_failure"] = train_df["is_failure"].to_numpy()
    test_out["is_failure"] = test_df["is_failure"].to_numpy()
    train_out.to_parquet(out_dir / "train.parquet", index=False)
    test_out.to_parquet(out_dir / "test.parquet", index=False)
    joblib.dump(preprocessor, artifact_dir / "preprocessor.joblib")
    report = {
        "raw_rows": int(len(raw)), "validated_rows": int(len(validated)), "clean_rows": int(len(clean)),
        "duplicate_rows_removed": duplicate_rows, "dropped_rows": int(len(raw)-len(clean)),
        "train_rows": int(len(train_out)), "test_rows": int(len(test_out)),
        "train_share": params["train_share"], "split_strategy": params["split_strategy"],
        "feature_count": len(feature_names), "features": feature_names,
        "target_distribution_train": {str(k): int(v) for k,v in train_df["is_failure"].value_counts().sort_index().items()},
        "target_distribution_test": {str(k): int(v) for k,v in test_df["is_failure"].value_counts().sort_index().items()},
        "preprocessor_fit_scope": "train_only", "dataset_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
    }
    (out_dir / "validation_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    if track_mlflow:
        mlflow.set_tracking_uri("sqlite:///mlflow.db")
        mlflow.set_experiment("lab4-data-pipeline")
        with mlflow.start_run(run_name="telemetry-data-preparation"):
            mlflow.log_params({"split_strategy": params["split_strategy"], "train_share": params["train_share"], "numeric_imputer": "median", "categorical_imputer": "most_frequent", "scaler": "StandardScaler", "encoder": "OneHotEncoder(handle_unknown=ignore)"})
            mlflow.log_metrics({k: float(report[k]) for k in ["raw_rows", "clean_rows", "duplicate_rows_removed", "train_rows", "test_rows", "feature_count"]})
            mlflow.log_artifact(str(out_dir / "validation_report.json"))
            mlflow.log_artifact(str(artifact_dir / "preprocessor.joblib"))
            mlflow.log_artifact(str(out_dir / "train.parquet"))
            mlflow.log_artifact(str(out_dir / "test.parquet"))
    return report

def main() -> None:
    report = run_pipeline()
    print(json.dumps(report, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
