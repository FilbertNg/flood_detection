"""Pooled training table for the ML trigger (build plan task ML1, Data Spec Table D).

One row per river station per quarter hour. Features are relative to each
station's own thresholds plus rain at rain stations within 10 / 25 km, tide
and calendar, so one model fits every station. Labels: does the level reach
the station's warning level within the next 1 / 2 h? No station identity is
used as a feature. Features at t use only data at or before t.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .. import tide as tide_mod
from . import network as river_network

STEP = "15min"
RAIN_WINDOWS = {"1h": 4, "2h": 8, "3h": 12, "6h": 24, "24h": 96}
RADII_KM = (10, 25)
UPSTREAM_FEATURES = ["up_rise_60m_max", "up_rise_120m_max", "up_level_rel_max"]
TIDE_COUPLING_STEPS, TIDE_COUPLING_MIN_PAIRS = 288, 96     # last 3 days, at least 24 h of valid pairs
# Label horizon is 2 h and flood-wave celerity on these rivers is ~1-2 m/s, so a station more than ~15 km
# upstream cannot influence the window. Applied when scripts/build_river_network.py writes the network.
UPSTREAM_MAX_KM = 15
FEATURES = (
    ["d_warning", "level_rel", "rise_15m", "rise_60m", "rise_120m"]
    + [f"rain_{w}_max_{r}km" for w in RAIN_WINDOWS for r in RADII_KM]
    + [f"rain_2to4h_max_{r}km" for r in RADII_KM]
    + ["rain_72h_ante_max_25km", "tide_height_m", "hours_to_high_tide", "tide_change_1h", "tide_coupling_3d"]
    + UPSTREAM_FEATURES
    + ["hour", "month"]
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


def default_network() -> dict[str, list[str]]:
    """config/river_network.yaml if present, else no upstream links."""
    return river_network.load_network(river_network.DEFAULT_PATH) if Path(river_network.DEFAULT_PATH).exists() else {}


def _level_state(level: pd.Series, meta) -> pd.DataFrame:
    """Level-derived columns of one river station on the common grid (past data only)."""
    span = meta.wl_danger_m - meta.wl_normal_m
    return pd.DataFrame({"level_rel": (level - meta.wl_normal_m) / span if span else np.nan,
                         "rise_15m": level - level.shift(1), "rise_60m": level - level.shift(4), "rise_120m": level - level.shift(8)})


def build_features(readings: pd.DataFrame, stations: pd.DataFrame, tide: pd.DataFrame | None = None,
                   wl_ids: list[str] | None = None, network: dict[str, list[str]] | None = None) -> pd.DataFrame:
    """Features for every river station and quarter hour (no labels).

    `network` maps a station to the stations upstream of it (default: config/river_network.yaml if present)."""
    if network is None:
        network = default_network()
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
        # tide valid at t itself (not the stale hour floor); see floodready.tide.tide_at for why that is not look-ahead.
        # Every path (training, replay, live forecast) comes through this function, so parity holds by construction.
        tide_grid = tide_mod.tide_at(tide, grid)

    frames = []
    wl = readings[readings.kind == "wl"].drop_duplicates(["graph_id", "time_local"], keep="last")
    wl_wide = wl.pivot(index="time_local", columns="graph_id", values="wl_m").reindex(grid)
    states: dict[str, pd.DataFrame] = {}

    def state_of(gid: str) -> pd.DataFrame | None:
        if gid not in states:
            usable = gid in wl_wide.columns and gid in wl_info.index
            states[gid] = _level_state(wl_wide[gid], wl_info.loc[gid]) if usable else None
        return states[gid]

    for graph_id in wl_ids:
        if graph_id not in wl_info.index:
            continue
        meta = wl_info.loc[graph_id]
        level = wl[wl.graph_id == graph_id].set_index("time_local")["wl_m"].reindex(grid)
        f = pd.DataFrame(index=grid)
        f["wl_m"], f["wl_warning_m"] = level, meta.wl_warning_m
        f["d_warning"] = level - meta.wl_warning_m
        f = f.join(_level_state(level, meta))

        if pd.notna(meta.lat):
            dist = pd.Series(haversine_km(meta.lat, meta.lon, rf_info.lat.to_numpy(), rf_info.lon.to_numpy()), index=rf_info.index)
        else:  # no coordinates: no rain features (the model handles missing values)
            dist = pd.Series(dtype=float)
        for r in RADII_KM:
            near = [g for g in dist[dist <= r].index if g in rain_cols]
            for w in RAIN_WINDOWS:
                f[f"rain_{w}_max_{r}km"] = rain[w][near].max(axis=1) if near else np.nan
            f[f"rain_2to4h_max_{r}km"] = rain["2to4h"][near].max(axis=1) if near else np.nan
        near25 = [g for g in dist[dist <= 25].index if g in rain_cols]
        f["rain_72h_ante_max_25km"] = rain["72h_ante"][near25].max(axis=1) if near25 else np.nan
        f["tide_height_m"] = tide_grid["tide_height_m"] if tide_grid is not None else np.nan
        f["hours_to_high_tide"] = tide_grid["hours_to_high_tide"] if tide_grid is not None else np.nan
        if tide_grid is not None:
            f["tide_change_1h"] = tide_grid["tide_height_m"] - tide_grid["tide_height_m"].shift(4)
            # how much this station's level moves with the tide over the last 3 days: tells a tide-driven river from a rain-driven one
            coupling = level.rolling(TIDE_COUPLING_STEPS, min_periods=TIDE_COUPLING_MIN_PAIRS).corr(tide_grid["tide_height_m"])
            f["tide_coupling_3d"] = coupling.replace([np.inf, -np.inf], np.nan).clip(-1, 1)   # a flat-lined gauge has no correlation
        else:
            f["tide_change_1h"] = f["tide_coupling_3d"] = np.nan
        up_states = [st for st in (state_of(u) for u in dict.fromkeys(network.get(graph_id, [])) if u != graph_id) if st is not None]
        for col, src in zip(UPSTREAM_FEATURES, ("rise_60m", "rise_120m", "level_rel")):
            f[col] = pd.concat([st[src] for st in up_states], axis=1).max(axis=1) if up_states else np.nan
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


def required_station_ids(stations: pd.DataFrame, wl_ids: list[str], network: dict[str, list[str]] | None = None) -> list[str]:
    """Every station whose readings the features need: the river stations, those upstream of them, and rain gauges within 25 km."""
    network = default_network() if network is None else network
    ids = set(wl_ids) | {u for g in wl_ids for u in network.get(g, [])}
    return sorted(ids | set(rain_stations_near(stations, wl_ids, km=25)))


def township_station_ids(town: dict, stations: pd.DataFrame, archived: set[str],
                         network: dict[str, list[str]] | None = None) -> list[str]:
    """Archived stations to load for a township: its own stations plus everything the ML features need
    (upstream river stations, rain within 25 km), so serving sees the same inputs as training."""
    wl_ids = [s["graph_id"] for s in town["stations"] if "WL" in s.get("types", [])]
    own = {s["graph_id"] for s in town["stations"]}
    return sorted((own | set(required_station_ids(stations, wl_ids, network))) & set(archived))


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
