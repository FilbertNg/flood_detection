"""Station features from 15-min JPS readings (build plan task E2).

Readings (long format): graph_id, kind ('rf' | 'wl'), time_local, rain_15min_mm, wl_m.
Stations: graph_id, kind, name, wl_alert_m, wl_warning_m, wl_danger_m.
Features at time t use only readings at or before t.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

STEP = pd.Timedelta(minutes=15)
RAIN_WINDOWS = {"st_rain_1h": 4, "st_rain_2h": 8, "st_rain_3h": 12, "st_rain_4h": 16, "st_rain_24h": 96}
FEATURE_COLUMNS = ["graph_id", "kind", "name", "time_local", "st_rain_1h", "st_rain_2h", "st_rain_3h", "st_rain_4h",
                   "st_rain_2to4h_max", "st_rain_24h", "n_missing_1h", "wl_m", "river_band", "river_rising",
                   "wl_alert_m", "wl_warning_m", "wl_danger_m", "is_stale"]


def _band(level: pd.Series, alert, warning, danger) -> pd.Series:
    if any(pd.isna(x) for x in (alert, warning, danger)):
        return pd.Series(None, index=level.index, dtype=object)
    band = np.select([level >= danger, level >= warning, level >= alert, level.notna()],
                     ["danger", "warning", "alert", "normal"], default=None)
    return pd.Series(band, index=level.index, dtype=object).where(level.notna(), None)


def compute_station_features(readings: pd.DataFrame, stations: pd.DataFrame, end: datetime | None = None,
                             stale_after_min: int = 120) -> pd.DataFrame:
    """Features for every station at every quarter hour up to `end` (vectorised; used by backfill)."""
    stale_steps = max(stale_after_min // 15, 1)
    info = stations.drop_duplicates(["graph_id", "kind"]).set_index(["graph_id", "kind"])
    frames = []
    for (graph_id, kind), group in readings.groupby(["graph_id", "kind"], sort=False):
        group = group.drop_duplicates("time_local", keep="last").set_index("time_local").sort_index()
        last = pd.Timestamp(end) if end is not None else group.index.max()
        grid = pd.date_range(group.index.min().floor("15min"), last, freq=STEP)
        if len(grid) == 0:
            continue
        out = pd.DataFrame(index=grid)
        meta = info.loc[(graph_id, kind)] if (graph_id, kind) in info.index else pd.Series(dtype=object)
        if kind == "rf":
            rain = group["rain_15min_mm"].reindex(grid)
            for col, n in RAIN_WINDOWS.items():
                out[col] = rain.rolling(n, min_periods=1).sum()
            out["st_rain_2to4h_max"] = out[["st_rain_2h", "st_rain_3h", "st_rain_4h"]].max(axis=1)
            out["n_missing_1h"] = rain.isna().astype(int).rolling(4, min_periods=1).sum()
            present = rain.notna()
        else:
            level = group["wl_m"].reindex(grid)
            last_level = level.ffill(limit=stale_steps)
            out["wl_m"] = last_level
            out["river_band"] = _band(last_level, meta.get("wl_alert_m"), meta.get("wl_warning_m"), meta.get("wl_danger_m"))
            out["river_rising"] = (last_level - last_level.shift(2)) > 0.01
            for col in ("wl_alert_m", "wl_warning_m", "wl_danger_m"):
                out[col] = meta.get(col)
            present = level.notna()
        out["is_stale"] = present.astype(int).rolling(stale_steps, min_periods=1).sum() == 0
        out["graph_id"], out["kind"], out["name"] = graph_id, kind, meta.get("name", graph_id)
        frames.append(out.rename_axis("time_local").reset_index())
    if not frames:
        return pd.DataFrame(columns=FEATURE_COLUMNS)
    return pd.concat(frames, ignore_index=True).reindex(columns=FEATURE_COLUMNS)


def station_features(readings: pd.DataFrame, at: datetime, stations: pd.DataFrame,
                     stale_after_min: int = 120) -> pd.DataFrame:
    """One row per (graph_id, kind) with features at time `at` (build plan §4.4)."""
    at = pd.Timestamp(at)
    window = readings[(readings.time_local > at - timedelta(hours=26)) & (readings.time_local <= at)]
    if window.empty:
        return pd.DataFrame(columns=FEATURE_COLUMNS)
    all_times = compute_station_features(window, stations, end=at, stale_after_min=stale_after_min)
    return all_times[all_times.time_local == at].reset_index(drop=True)
