import json
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
from joblib import load
from pandas.api.types import CategoricalDtype
import lightgbm as lgb

# Project base directory (two levels up from this file:
#   project_root/prediction_app/model.py)
BASE_DIR = Path(__file__).resolve().parent.parent

# Paths to data and model artifacts used for inference
DATA_PARQUET = BASE_DIR / "Prediction" / "Smart-Parking" / "parking_with_weather.parquet"
ARTIFACT_DIR = BASE_DIR / "Prediction" / "Smart-Parking" / "models" / "parking_occ_lgbm"


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    ts = pd.to_datetime(df["timestamp_utc"], utc=True)
    df["hour"] = ts.dt.hour.astype("int16")
    df["dow"] = ts.dt.weekday.astype("int8")
    df["month"] = ts.dt.month.astype("int8")
    df["is_weekend"] = df["dow"].isin([5, 6]).astype("int8")
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24).astype("float32")
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24).astype("float32")
    return df


def add_rate_and_lags(df: pd.DataFrame) -> pd.DataFrame:
    if "occ_rate" not in df.columns:
        if "total_spaces" in df.columns and "occupied_spaces" in df.columns:
            cap = df["total_spaces"].replace(0, np.nan)
            df["occ_rate"] = (df["occupied_spaces"] / cap).clip(0, 1)
        else:
            df["occ_rate"] = np.nan

    df = df.sort_values(["external_id", "timestamp_utc"])

    df["occ_rate_lag1h"] = df.groupby("external_id", observed=False)["occ_rate"].shift(1)
    df["occ_rate_lag24h"] = df.groupby("external_id", observed=False)["occ_rate"].shift(24)
    df["occ_rate_roll3h"] = (
        df.groupby("external_id", observed=False)["occ_rate"]
        .rolling(window=3, min_periods=1)
        .mean()
        .reset_index(level=0, drop=True)
    )
    return df


def load_artifacts_for_prediction(artifact_dir: Path | str) -> Tuple[lgb.Booster, object, dict]:
    art = Path(artifact_dir)
    spec = json.loads((art / "feature_spec.json").read_text())
    calibrator = load(art / "calibrator.joblib")
    model = lgb.Booster(model_file=str(art / "model.txt"))
    return model, calibrator, spec


def prepare_single_input(df_row: pd.DataFrame, spec: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    features = spec["features"]
    train_cats = spec["external_id_categories"]

    df = df_row.copy()
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df = add_time_features(df)

    for lag in ["occ_rate_lag1h", "occ_rate_lag24h", "occ_rate_roll3h"]:
        if lag not in df.columns:
            df[lag] = np.nan

    cat_dtype = CategoricalDtype(categories=train_cats, ordered=True)
    df["external_id"] = df["external_id"].astype(str).astype(cat_dtype)

    for f in features:
        if f not in df.columns:
            df[f] = np.nan

    return df[features], df


def predict_single(df_row: pd.DataFrame, artifact_dir: Path | str) -> pd.DataFrame:
    """
    Given a single-row DataFrame describing a parking lot and a timestamp,
    compute features, run the model, and return a DataFrame with:
      - p_busy
      - predicted_occupied
      - predicted_free
    """
    model, calibrator, spec = load_artifacts_for_prediction(artifact_dir)
    features, full_df = prepare_single_input(df_row, spec)

    # Probability of lot being busy
    p_busy = calibrator.predict_proba(features)[:, 1].item()

    # Convert probability into occupied / free counts
    cap = full_df["total_spaces"].iloc[0]
    if pd.isna(cap):
        predicted_occupied = None
        predicted_free = None
    else:
        cap_int = int(cap)
        predicted_occupied = int(np.clip(round(p_busy * cap_int), 0, cap_int))
        predicted_free = cap_int - predicted_occupied

    out = full_df.copy()
    out["p_busy"] = p_busy
    out["predicted_occupied"] = predicted_occupied
    out["predicted_free"] = predicted_free
    return out


try:
    df = pd.read_parquet(DATA_PARQUET)
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df = add_time_features(df)
    df = add_rate_and_lags(df)
except Exception as exc:  # pragma: no cover - defensive fallback
    # Training DataFrame is only used as a fallback for lag features.
    # If it cannot be loaded, we log and fall back to an empty DataFrame.
    print(f"Warning: failed to load training data from {DATA_PARQUET}: {exc}")
    df = pd.DataFrame()

