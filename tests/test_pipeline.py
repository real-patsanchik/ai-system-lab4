from pathlib import Path
import pandas as pd
import pytest
from pandera.errors import SchemaErrors
from src.contracts import validate_raw_telemetry
from src.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parents[1]

def test_valid_dataset_runs_and_outputs_are_created(tmp_path):
    report = run_pipeline(ROOT / "data/raw/telemetry.csv", tmp_path / "processed", tmp_path / "artifacts", track_mlflow=False)
    assert report["raw_rows"] > report["clean_rows"]
    assert report["train_rows"] + report["test_rows"] == report["clean_rows"]
    assert report["preprocessor_fit_scope"] == "train_only"
    assert (tmp_path / "processed/train.parquet").exists()
    assert (tmp_path / "processed/test.parquet").exists()
    assert (tmp_path / "processed/validation_report.json").exists()
    assert (tmp_path / "artifacts/preprocessor.joblib").exists()

def test_invalid_pressure_is_rejected():
    df = pd.read_csv(ROOT / "data/raw/telemetry.csv", parse_dates=["timestamp"]).iloc[:10].copy()
    df.loc[df.index[0], "pressure"] = -1
    with pytest.raises(SchemaErrors):
        validate_raw_telemetry(df)

def test_invalid_operating_mode_is_rejected():
    df = pd.read_csv(ROOT / "data/raw/telemetry.csv", parse_dates=["timestamp"]).iloc[:10].copy()
    df.loc[df.index[0], "operating_mode"] = "SPORT"
    with pytest.raises(SchemaErrors):
        validate_raw_telemetry(df)

def test_invalid_device_id_is_rejected():
    df = pd.read_csv(ROOT / "data/raw/telemetry.csv", parse_dates=["timestamp"]).iloc[:10].copy()
    df.loc[df.index[0], "device_id"] = "DEVICE_1"
    with pytest.raises(SchemaErrors):
        validate_raw_telemetry(df)
