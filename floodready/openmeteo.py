"""Open-Meteo forecast logging: every hourly response is stored, building our
own archive of real forecasts (Training Data Spec, Dataset 2)."""
from __future__ import annotations

from datetime import datetime

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def forecast_params(points: list[dict], models: list[str]) -> dict:
    return {
        "latitude": ",".join(str(p["lat"]) for p in points),
        "longitude": ",".join(str(p["lon"]) for p in points),
        "hourly": "precipitation,precipitation_probability",
        "models": ",".join(models),
        "past_hours": 6,
        "forecast_hours": 48,
        "timezone": "Asia/Kuala_Lumpur",
    }


def flatten_forecast(payload, point_ids: list[str], models: list[str]) -> list[dict]:
    """One row per point, model and hour. A multi-point response is a list in
    request order; with several models each variable gets a _<model> suffix."""
    locations = payload if isinstance(payload, list) else [payload]
    rows = []
    for point_id, location in zip(point_ids, locations):
        hourly = location["hourly"]
        for model in models:
            suffix = f"_{model}" if len(models) > 1 else ""
            precip = hourly.get(f"precipitation{suffix}", [])
            prob = hourly.get(f"precipitation_probability{suffix}", [])
            for i, stamp in enumerate(hourly["time"]):
                rows.append({
                    "point_id": point_id,
                    "model": model,
                    "grid_lat": location["latitude"],
                    "grid_lon": location["longitude"],
                    "time_local": datetime.fromisoformat(stamp),
                    "precip_mm": precip[i] if i < len(precip) else None,
                    "precip_prob_pct": prob[i] if i < len(prob) else None,
                })
    return rows
