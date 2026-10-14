"""Hourly tide for Port Klang (build plan task G3).

Source: Open-Meteo Marine `sea_level_height_msl` at an offshore point near
Port Klang (model data; the docs warn coastal accuracy is limited). Cross-check
against JUPEM tide tables before quoting tide in public material.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
PORT_KLANG_OFFSHORE = (2.95, 101.25)


def marine_params(start: str, end: str, lat: float = PORT_KLANG_OFFSHORE[0], lon: float = PORT_KLANG_OFFSHORE[1]) -> dict:
    return {"latitude": lat, "longitude": lon, "hourly": "sea_level_height_msl", "start_date": start,
            "end_date": end, "timezone": "Asia/Kuala_Lumpur", "cell_selection": "sea"}


def series_from_marine(payload: dict) -> pd.Series:
    hourly = payload["hourly"]
    values = [np.nan if v is None else float(v) for v in hourly["sea_level_height_msl"]]
    return pd.Series(values, index=pd.to_datetime(hourly["time"]), name="tide_height_m")


def high_tide_times(series: pd.Series) -> pd.DatetimeIndex:
    """Local maxima: higher than both neighbours (first of equal pairs)."""
    s = series.interpolate(limit=2)
    is_high = (s > s.shift(1)) & (s >= s.shift(-1))
    return s.index[is_high.fillna(False).to_numpy()]


def tide_features(series: pd.Series) -> pd.DataFrame:
    """tide_height_m and signed hours to the nearest high tide (+ = coming, - = past)."""
    highs = high_tide_times(series).to_numpy()
    times = series.index.to_numpy()
    nearest = np.full(len(times), np.nan)
    if len(highs):
        pos = np.searchsorted(highs, times)
        nxt = highs[np.minimum(pos, len(highs) - 1)]
        prv = highs[np.maximum(pos - 1, 0)]
        to_next = (nxt - times) / np.timedelta64(1, "h")
        to_prev = (prv - times) / np.timedelta64(1, "h")
        to_next = np.where(to_next < 0, np.inf, to_next)
        to_prev = np.where(to_prev > 0, -np.inf, to_prev)
        nearest = np.where(to_next <= -to_prev, to_next, to_prev)
        nearest = np.where(np.isfinite(nearest), nearest, np.nan)
    return pd.DataFrame({"time_local": series.index, "tide_height_m": series.to_numpy(),
                         "hours_to_high_tide": nearest})
