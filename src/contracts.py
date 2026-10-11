"""Input data contract for industrial telemetry."""
from __future__ import annotations
import pandas as pd
try:
    import pandera.pandas as pa
except ImportError:  # compatibility with older Pandera releases
    import pandera as pa
Check, Column, DataFrameSchema = pa.Check, pa.Column, pa.DataFrameSchema

RawTelemetrySchema = DataFrameSchema({
    "device_id": Column(str, Check.str_matches(r"^DEV_\d{4}$"), nullable=False),
    "timestamp": Column(pa.DateTime, nullable=False),
    "temperature": Column(float, Check.in_range(-40.0, 180.0), nullable=True, coerce=True),
    "vibration": Column(float, Check.greater_than_or_equal_to(0.0), nullable=True, coerce=True),
    "pressure": Column(float, Check.in_range(0.5, 30.0), nullable=False, coerce=True),
    "operating_mode": Column(str, Check.isin(["ECO", "NORMAL", "TURBO"]), nullable=False),
    "is_failure": Column(int, Check.isin([0, 1]), nullable=False, coerce=True),
}, strict=True, coerce=True)

def validate_raw_telemetry(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate schema and value ranges; raises SchemaError on invalid input."""
    return RawTelemetrySchema.validate(frame, lazy=True)
