from typing import Dict, Optional, Any

import json

import numpy as np
import pandas as pd
import requests
from django.http import JsonResponse, HttpRequest, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt

from prediction_app.model import ARTIFACT_DIR, predict_single, df as TRAIN_DF


WEATHER_VARS = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "cloud_cover",
    "wind_speed_10m",
    "wind_direction_10m",
]

LAG_VARS = [
    "occ_rate_lag1h",
    "occ_rate_lag24h",
    "occ_rate_roll3h",
]


def _to_occupied_count(occ: Any) -> float:
    """
    Normalize occupied_spots field into a numeric count.

    - If it's a list of IDs, returns len(list).
    - If it's a single-element list with a numeric string (e.g. ["15"]), use that value.
    - If it's a scalar string like "15", converts directly.
    """
    if isinstance(occ, (list, tuple)):
        if len(occ) == 1:
            try:
                return float(occ[0])
            except (TypeError, ValueError):
                return float(len(occ))
        return float(len(occ))
    return float(occ)


def compute_lags_from_events(
    events: Any,
    total_spaces: Any,
    prediction_ts: Any,
    occupied_spots_24h_ago: Optional[Any] = None,
) -> Dict[str, Optional[float]]:
    """
    Compute lag features from a list of occupancy events over the last ~3 hours.

    Each event is expected to have:
      - "timestamp": ISO8601 string
      - "occupied_spots": either a count (string/int) or a list of spot IDs / a
        single-element list containing the count.

    Semantics: occupancy is treated as stepwise-constant between events; if
    there are no events in the last 3h, the latest event is carried forward.
    """
    rows = []
    for e in events or []:
        ts = e.get("timestamp")
        occ = e.get("occupied_spots")
        if ts is None or occ is None:
            continue
        rows.append(
            {
                "timestamp_utc": ts,
                "occupied_spaces": _to_occupied_count(occ),
            }
        )

    if not rows:
        return {k: None for k in LAG_VARS}

    df_events = pd.DataFrame(rows)
    df_events["timestamp_utc"] = pd.to_datetime(df_events["timestamp_utc"], utc=True)
    df_events = df_events.sort_values("timestamp_utc")

    cap = float(total_spaces) if total_spaces is not None else np.nan
    df_events["occ_rate"] = (df_events["occupied_spaces"] / cap).clip(0, 1)

    prediction_ts = pd.to_datetime(prediction_ts, utc=True)

    def occ_at(ts_point: pd.Timestamp) -> Optional[float]:
        mask = df_events["timestamp_utc"] <= ts_point
        if not mask.any():
            return None
        return float(df_events.loc[mask, "occ_rate"].iloc[-1])

    # 1h lag: occupancy at t-1h
    t1 = prediction_ts - pd.Timedelta(hours=1)
    occ_rate_lag1h = occ_at(t1)

    # 3h rolling mean over [t-3h, t], stepwise-constant occupancy
    window_start = prediction_ts - pd.Timedelta(hours=3)
    window_end = prediction_ts

    event_times = df_events[
        (df_events["timestamp_utc"] >= window_start)
        & (df_events["timestamp_utc"] <= window_end)
    ]["timestamp_utc"].tolist()

    times = [window_start] + event_times + [window_end]
    times = sorted(set(times))

    total_area = 0.0
    for t_start, t_end in zip(times[:-1], times[1:]):
        occ = occ_at(t_start)
        if occ is None:
            continue
        duration_hours = (t_end - t_start).total_seconds() / 3600.0
        total_area += occ * duration_hours

    window_length_hours = 3.0
    occ_rate_roll3h = total_area / window_length_hours if window_length_hours > 0 else None

    # 24h lag from a single value if provided
    if occupied_spots_24h_ago is not None and cap and not np.isnan(cap):
        try:
            occ24 = float(occupied_spots_24h_ago)
            occ_rate_lag24h = occ24 / cap
        except (TypeError, ValueError):
            occ_rate_lag24h = None
    else:
        occ_rate_lag24h = None

    return {
        "occ_rate_lag1h": occ_rate_lag1h,
        "occ_rate_lag24h": occ_rate_lag24h,
        "occ_rate_roll3h": occ_rate_roll3h,
    }


def fetch_current_weather_from_open_meteo(lat: float, lon: float) -> Dict[str, Optional[float]]:
    """
    Fetch current weather conditions from Open-Meteo for the given location.

    Returns a dict with keys matching WEATHER_VARS; missing values are None.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": ",".join(WEATHER_VARS),
        "timezone": "UTC",
    }
    try:
        resp = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        current = data.get("current", {})
    except Exception as exc:
        # Network or API error; fall back to None values
        print(f"Warning: failed to fetch weather from Open-Meteo: {exc}")
        current = {}

    return {var: current.get(var) for var in WEATHER_VARS}


def compute_occ_rate_lags(external_id: str) -> Dict[str, Optional[float]]:
    """
    Determine occupancy-rate lag features for a lot.

    Integration points:
      - First, you can plug your database lookup here.
      - If DB data is unavailable, we fall back to the historical training
        DataFrame (TRAIN_DF) loaded in model.py. That data may be old,
        but it's a reasonable fallback.
    """
    lags: Dict[str, Optional[float]] = {k: None for k in LAG_VARS}

    # TODO: plug in your DB lookup here (optional).

    # Fallback to historical training data (parquet) if available.
    if TRAIN_DF is not None and not TRAIN_DF.empty:
        lot_df = TRAIN_DF[TRAIN_DF["external_id"] == external_id]
        if not lot_df.empty:
            lot_df = lot_df.sort_values("timestamp_utc")
            last = lot_df.iloc[-1]
            for var in LAG_VARS:
                if var in last.index and pd.notna(last[var]):
                    lags[var] = float(last[var])

    return lags


@csrf_exempt
def predict_view(request: HttpRequest) -> JsonResponse | HttpResponseBadRequest:
    """
    Django view that exposes the /predict endpoint.

    Expects a JSON body with:
      - required: timestamp_utc, lat, lon, total_spaces
      - optional: external_id, WEATHER_VARS, LAG_VARS
    """
    if request.method != "POST":
        return HttpResponseBadRequest("Only POST requests are allowed.")

    try:
        payload: Dict[str, Any] = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON payload.")

    required_fields = ["timestamp_utc", "lat", "lon", "total_spaces"]
    missing = [f for f in required_fields if f not in payload]
    if missing:
        return HttpResponseBadRequest(f"Missing required fields: {', '.join(missing)}")

    req_dict = dict(payload)

    # If event history is provided, derive lag features from it.
    events = req_dict.get("events")
    prediction_ts = req_dict.get("prediction_timestamp") or req_dict.get("timestamp_utc")
    occupied_spots_24h_ago = req_dict.get("occupied_spots_24h_ago")

    if events and prediction_ts:
        lags_from_events = compute_lags_from_events(
            events=events,
            total_spaces=req_dict["total_spaces"],
            prediction_ts=prediction_ts,
            occupied_spots_24h_ago=occupied_spots_24h_ago,
        )
        for var, value in lags_from_events.items():
            if value is not None:
                req_dict[var] = value

    # Fetch weather if any weather field is missing
    if any(req_dict.get(var) is None for var in WEATHER_VARS):
        fetched_weather = fetch_current_weather_from_open_meteo(
            float(req_dict["lat"]),
            float(req_dict["lon"]),
        )
        for var, value in fetched_weather.items():
            # Only fill fields that were not provided by the caller
            if req_dict.get(var) is None and value is not None:
                req_dict[var] = value

    # Fill occupancy-rate lag features if not supplied by the caller and
    # an external_id is available to look them up with.
    external_id = req_dict.get("external_id")
    if external_id is not None and any(req_dict.get(var) is None for var in LAG_VARS):
        lag_values = compute_occ_rate_lags(str(external_id))
        for var, value in lag_values.items():
            if req_dict.get(var) is None and value is not None:
                req_dict[var] = value

    # Build a single-row DataFrame from the (possibly enriched) request
    df_row = pd.DataFrame([req_dict])

    # Use the prediction pipeline
    result_df = predict_single(df_row, ARTIFACT_DIR)
    row = result_df.iloc[0]

    predicted_occupied = row.get("predicted_occupied")
    predicted_free = row.get("predicted_free")

    # Derive a simple, explainable confidence score and label.
    confidence_score = 1.0
    confidence_reasons: list[str] = []

    # Penalize missing external_id (no historical lag lookup).
    if external_id is None:
        confidence_score -= 0.3
        confidence_reasons.append("external_id_missing")

    # Penalize missing lag features after all enrichments.
    if any(req_dict.get(var) is None for var in LAG_VARS):
        confidence_score -= 0.2
        confidence_reasons.append("lags_not_available")

    # Penalize missing weather fields after attempted fetch.
    if any(req_dict.get(var) is None for var in WEATHER_VARS):
        confidence_score -= 0.1
        confidence_reasons.append("weather_imputed_or_missing")

    # Penalize probabilities close to the decision boundary.
    p_busy = float(row["p_busy"])
    if 0.4 <= p_busy <= 0.6:
        confidence_score -= 0.2
        confidence_reasons.append("p_busy_near_decision_boundary")

    # Clamp score to [0, 1].
    confidence_score = max(0.0, min(1.0, confidence_score))

    if confidence_score >= 0.75:
        confidence_level = "high"
    elif confidence_score >= 0.5:
        confidence_level = "medium"
    else:
        confidence_level = "low"

    response_payload = {
        "external_id": str(row["external_id"]) if "external_id" in row else req_dict.get("external_id"),
        "timestamp_utc": str(row["timestamp_utc"]),
        "p_busy": p_busy,
        "predicted_occupied": int(predicted_occupied) if pd.notna(predicted_occupied) else None,
        "predicted_free": int(predicted_free) if pd.notna(predicted_free) else None,
        "confidence_score": confidence_score,
        "confidence_level": confidence_level,
        "confidence_reasons": confidence_reasons,
    }

    return JsonResponse(response_payload)
