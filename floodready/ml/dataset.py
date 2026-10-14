"""Pooled training table for the ML trigger (build plan task ML1, Data Spec Table D).

One row per river station per quarter hour. Features are relative to each
station's own thresholds plus rain at rain stations within 10 / 25 km, tide
and calendar, so one model fits every station. Labels: does the level reach
the station's warning level within the next 1 / 2 h? No station identity is
used as a feature. Features at t use only data at or before t.
"""
from __future__ import annotations


import numpy as np
import pandas as pd

STEP = "15min"
RAIN_WINDOWS = {"1h": 4, "2h": 8, "3h": 12, "6h": 24, "24h": 96}
RADII_KM = (10, 25)
FEATURES = (
    ["d_alert", "d_warning", "d_danger", "level_rel", "rise_15m", "rise_60m", "rise_120m"]
    + [f"rain_{w}_{agg}_{r}km" for w in RAIN_WINDOWS for agg in ("max", "mean") for r in RADII_KM]
    + [f"rain_2to4h_max_{r}km" for r in RADII_KM]
    + ["rain_72h_ante_max_25km", "n_rf_10km", "n_rf_25km", "tide_height_m", "hours_to_high_tide", "hour", "month"]
)


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = p2 - p1, np.radians(np.asarray(lon2) - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def _rain_sums(readings: pd.DataFrame, grid: pd.DatetimeIndex) -> dict[str, pd.DataFrame]:
    """Rolling rain sums per rain station on the common grid (missing quarters count as 0)."""
    rf = readings[readings.kind == "rf"].drop_duplicates(["graph_id", "time_local"], keep="last")
    wide = rf.pivot(index="time_local", columns="graph_id", values="rain_15min_mm").reindex(grid).fillna(0.0)
    sums = {w: wide.rolling(n, min_periods=1).sum() for w, n in RAIN_WINDOWS.items()}
    sums["2to4h"] = pd.concat([wide.rolling(n, min_periods=1).sum() for n in (8, 12, 16)]).groupby(level=0).max()
    sums["72h_ante"] = wide.rolling(288, min_periods=1).sum().shift(96)
    return sums


def build_features(readings: pd.DataFrame, stations: pd.DataFrame, tide: pd.DataFrame | None = None,
                   wl_ids: list[str] | None = None) -> pd.DataFrame:
    """Features for every river station and quarter hour (no labels)."""
    grid = pd.date_range(readings.time_local.min().floor(STEP), readings.time_local.max(), freq=STEP)
    info = stations.drop_duplicates(["graph_id", "kind"])
    wl_info = info[(info.kind == "wl") & info.thresholds_ok.astype(bool)].set_index("graph_id")
    rf_info = info[(info.kind == "rf") & info.lat.notna()].set_index("graph_id")
    rain = _rain_sums(readings, grid)
    rain_cols = set(rain["1h"].columns)
    if wl_ids is None:
        wl_ids = sorted(set(readings[readings.kind == "wl"].graph_id) & set(wl_info.index))

    tide_grid = None
    if tide is not None and len(tide):
        hourly = tide.set_index("time_local")[["tide_height_m", "hours_to_high_tide"]]
        tide_grid = hourly.reindex(grid.floor("h")).set_axis(grid)

    frames = []
    wl = readings[readings.kind == "wl"].drop_duplicates(["graph_id", "time_local"], keep="last")
    for graph_id in wl_ids:
        if graph_id not in wl_info.index:
            continue
        meta = wl_info.loc[graph_id]
        level = wl[wl.graph_id == graph_id].set_index("time_local")["wl_m"].reindex(grid)
        f = pd.DataFrame(index=grid)
        f["wl_m"], f["wl_warning_m"] = level, meta.wl_warning_m
        f["d_alert"], f["d_warning"], f["d_danger"] = level - meta.wl_alert_m, level - meta.wl_warning_m, level - meta.wl_danger_m
        span = meta.wl_danger_m - meta.wl_normal_m
        f["level_rel"] = (level - meta.wl_normal_m) / span if span else np.nan
        for name, k in (("rise_15m", 1), ("rise_60m", 4), ("rise_120m", 8)):
            f[name] = level - level.shift(k)

        if pd.notna(meta.lat):
            dist = pd.Series(haversine_km(meta.lat, meta.lon, rf_info.lat.to_numpy(), rf_info.lon.to_numpy()), index=rf_info.index)
        else:  # no coordinates: no rain features (the model handles missing values)
            dist = pd.Series(dtype=float)
        for r in RADII_KM:
            near = [g for g in dist[dist <= r].index if g in rain_cols]
            f[f"n_rf_{r}km"] = len(near)
            for w in RAIN_WINDOWS:
                block = rain[w][near] if near else None
                f[f"rain_{w}_max_{r}km"] = block.max(axis=1) if near else np.nan
                f[f"rain_{w}_mean_{r}km"] = block.mean(axis=1) if near else np.nan
            f[f"rain_2to4h_max_{r}km"] = rain["2to4h"][near].max(axis=1) if near else np.nan
        near25 = [g for g in dist[dist <= 25].index if g in rain_cols]
        f["rain_72h_ante_max_25km"] = rain["72h_ante"][near25].max(axis=1) if near25 else np.nan
        f["tide_height_m"] = tide_grid["tide_height_m"] if tide_grid is not None else np.nan
        f["hours_to_high_tide"] = tide_grid["hours_to_high_tide"] if tide_grid is not None else np.nan
        f["hour"], f["month"] = grid.hour + grid.minute / 60, grid.month
        f["graph_id"] = graph_id
        frames.append(f.rename_axis("time_local").reset_index())
    cols = ["graph_id", "time_local", "wl_m", "wl_warning_m"] + FEATURES
    if not frames:
        return pd.DataFrame(columns=cols)
    return pd.concat(frames, ignore_index=True)[cols]


def add_labels(features: pd.DataFrame) -> pd.DataFrame:
    """cross_1h / cross_2h: the level reaches the station's warning level within the next 1 / 2 h."""
    out = []
    for _, g in features.groupby("graph_id", sort=False):
        g = g.sort_values("time_local").copy()
        level = g["wl_m"].reset_index(drop=True)
        for name, k in (("cross_1h", 4), ("cross_2h", 8)):
            future_max = level[::-1].rolling(k, min_periods=1).max()[::-1].shift(-1)
            label = (future_max >= g["wl_warning_m"].to_numpy()).astype(float)
            label[future_max.isna()] = np.nan
            g[name] = label.to_numpy()
        out.append(g)
    return pd.concat(out, ignore_index=True)


def fold_of(times: pd.Series) -> pd.Series:
    """Time-blocked fold: calendar quarters assigned round-robin to 4 folds."""
    times = pd.to_datetime(pd.Series(times))
    return ((times.dt.year * 4 + (times.dt.month - 1) // 3) % 4).astype(int).to_numpy()


def training_rows(table: pd.DataFrame) -> pd.DataFrame:
    """Rows below warning with known labels, plus a time-blocked fold (calendar quarters, round-robin)."""
    rows = table[table.wl_m.notna() & (table.wl_m < table.wl_warning_m) & table.cross_2h.notna()].copy()
    rows["fold"] = fold_of(rows.time_local)
    return rows.reset_index(drop=True)


def rain_stations_near(stations: pd.DataFrame, wl_ids: list[str], km: float = 25,
                       available: set[str] | None = None) -> list[str]:
    """Rain stations (with coordinates) within `km` of any of the river stations; optionally only `available` ones."""
    wl = stations[(stations.kind == "wl") & stations.graph_id.isin(wl_ids) & stations.lat.notna()]
    rf = stations[(stations.kind == "rf") & stations.lat.notna()]
    near: set[str] = set()
    for _, w in wl.iterrows():
        d = haversine_km(w.lat, w.lon, rf.lat.to_numpy(), rf.lon.to_numpy())
        near |= set(rf.graph_id[d <= km])
    if available is not None:
        near &= set(available)
    return sorted(near)
