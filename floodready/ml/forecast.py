"""River-level forecast (improvement #12): the level at +1 h and +2 h with a p10-p90 range.

One pooled HistGradientBoostingRegressor(loss="quantile") per horizon and quantile (0.1, 0.5, 0.9)
predicts the CHANGE in level (m); the current level is added back, so one model serves every
station (features are the station-relative columns of `dataset.build_features`; the list comes from
the bundle, never hard-coded). Rows at any level are used for training, not only below warning:
a forecast is needed while the river is already high, and dropping those rows would teach the
model that rivers never rise past warning. Folds are the trigger's time-blocked folds, and the
fold models serve out-of-sample replays of past events. Features at t use only data at or before t.
"""
from __future__ import annotations

import hashlib
import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from . import dataset

log = logging.getLogger(__name__)

HORIZONS = {"1h": 4, "2h": 8}                  # name -> quarter-hour steps ahead
QUANTILES = (0.1, 0.5, 0.9)
MODEL_PARAMS = {"max_iter": 200, "learning_rate": 0.05, "max_leaf_nodes": 31, "min_samples_leaf": 40,
                "l2_regularization": 1.0, "early_stopping": False, "random_state": 0}


def _key(horizon: str, q: float) -> str:
    return f"{horizon}_p{round(q * 100)}"


def add_targets(table: pd.DataFrame) -> pd.DataFrame:
    """d1h / d2h: level at t+1 h / t+2 h minus level at t (NaN when either is unknown)."""
    out = []
    for _, g in table.groupby("graph_id", sort=False):
        g = g.sort_values("time_local").copy()
        for name, k in HORIZONS.items():
            g[f"d{name}"] = (g["wl_m"].shift(-k) - g["wl_m"]).to_numpy()
        out.append(g)
    return pd.concat(out, ignore_index=True) if out else table.assign(d1h=np.nan, d2h=np.nan)


def training_rows(table: pd.DataFrame) -> pd.DataFrame:
    """Rows where the current and both future levels are known (any level), with the trigger's time-blocked fold."""
    rows = table[table.wl_m.notna() & table.d1h.notna() & table.d2h.notna()].copy()
    rows["fold"] = dataset.fold_of(rows.time_local)
    return rows.reset_index(drop=True)


def _fit_models(rows: pd.DataFrame, features: list[str]) -> dict:
    models = {}
    for h in HORIZONS:
        for q in QUANTILES:
            m = HistGradientBoostingRegressor(loss="quantile", quantile=q, **MODEL_PARAMS)
            models[_key(h, q)] = m.fit(rows[features], rows[f"d{h}"])
    return models


def tide_signature(tide: pd.DataFrame | None) -> dict | None:
    """Fingerprint of the tide table a model trained on (row count, last time, hash of the heights)."""
    if tide is None or not len(tide):
        return None
    heights = pd.to_numeric(tide["tide_height_m"], errors="coerce").round(4).to_numpy()
    return {"rows": int(len(tide)), "max_time": str(tide["time_local"].max()),
            "sha1": hashlib.sha1(heights.tobytes()).hexdigest()[:16]}


def fit(rows: pd.DataFrame, features: list[str], rain_ids: list[str] | None = None,
        tide: pd.DataFrame | None = None) -> dict:
    """`rain_ids`: the rain gauges the features were built from; serving restricts to the same list so the
    forecast does not drift as the archive grows. `tide`: fingerprinted into the bundle."""
    return {"models": _fit_models(rows, list(features)), "features": list(features), "params": MODEL_PARAMS,
            "quantiles": QUANTILES, "horizons": dict(HORIZONS),
            "trained_folds": sorted(int(f) for f in rows.fold.unique()) if "fold" in rows else [],
            "rain_ids": sorted(rain_ids) if rain_ids is not None else None, "tide_signature": tide_signature(tide),
            "trained_at": datetime.now().isoformat(timespec="seconds")}


def predict_changes(bundle: dict, X: pd.DataFrame) -> dict[str, np.ndarray]:
    """{horizon: (n, 3) array of the p10 / p50 / p90 change}, sorted per row so quantiles never cross."""
    X = X[bundle["features"]]
    out = {}
    for h in HORIZONS:
        raw = np.column_stack([bundle["models"][_key(h, q)].predict(X) for q in QUANTILES])
        out[h] = np.sort(raw, axis=1)
    return out


def cross_val_changes(rows: pd.DataFrame, features: list[str], models_out: dict | None = None,
                      rain_ids: list[str] | None = None, tide: pd.DataFrame | None = None) -> pd.DataFrame:
    """Out-of-fold predicted changes: each fold is predicted by a model that never saw it.
    Columns `{h}_p10/p50/p90`. Pass a dict as `models_out` to keep each fold's bundle."""
    features = list(features)
    cols = [_key(h, q) for h in HORIZONS for q in QUANTILES]
    oof = pd.DataFrame(index=rows.index, columns=cols, dtype=float)
    for fold in sorted(rows.fold.unique()):
        test = rows.fold == fold
        bundle = fit(rows[~test], features, rain_ids, tide)
        pred = predict_changes(bundle, rows.loc[test])
        for h in HORIZONS:
            for i, q in enumerate(QUANTILES):
                oof.loc[test, _key(h, q)] = pred[h][:, i]
        if models_out is not None:
            models_out[int(fold)] = bundle
    return oof


def save_bundle(bundle: dict, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, path, compress=3)


def load_or_none(path: Path) -> dict | None:
    try:
        return joblib.load(path)
    except Exception as exc:  # missing file, version mismatch...
        log.warning("Forecast model unavailable (%s): no river forecast", exc)
        return None


def bundle_for(models_dir: Path, when: datetime, live: bool, name: str = "forecast_v1") -> dict | None:
    """Live: the final model. Replaying the past: the fold model trained WITHOUT that period."""
    models_dir = Path(models_dir)
    if not live:
        fold = int(dataset.fold_of(pd.Series([pd.Timestamp(when)]))[0])
        bundle = load_or_none(models_dir / f"{name}_oof{fold}.joblib")
        if bundle is not None:
            return {**bundle, "out_of_sample": True}
    bundle = load_or_none(models_dir / f"{name}.joblib")
    return {**bundle, "out_of_sample": False} if bundle is not None else None


def _iso(t: pd.Timestamp) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%S+08:00")


def river_forecast(bundle: dict, feats: pd.DataFrame, graph_id: str, at: datetime) -> dict | None:
    """The shape of `RiverForecast` (packages/shared/src/api/types.ts), or None if the station's level at
    `at` is unknown or the bundle needs a feature `feats` does not have. `feats` comes from
    `dataset.build_features`; only its row at `at` (the latest quarter hour up to `at`) is used."""
    missing = [c for c in bundle["features"] if c not in feats.columns]
    if missing:
        log.warning("forecast model expects missing features %s: no river forecast", missing)
        return None
    at = pd.Timestamp(at)
    mine = feats[(feats.graph_id == graph_id) & (feats.time_local <= at) &
                 (feats.time_local > at - timedelta(minutes=15))]
    if mine.empty:
        return None
    row = mine.sort_values("time_local").iloc[[-1]]
    now = float(row.wl_m.iloc[0])
    if np.isnan(now):
        return None
    changes = predict_changes(bundle, row)
    points = []
    for h, k in HORIZONS.items():
        p10, p50, p90 = (round(now + float(c), 2) for c in changes[h][0])
        points.append({"time": _iso(at + timedelta(minutes=15 * k)), "wl_m": p50, "wl_m_p10": p10, "wl_m_p90": p90})
    warning = row.wl_warning_m.iloc[0] if "wl_warning_m" in row else np.nan
    return {"graph_id": graph_id, "wl_now_m": round(now, 2), "wl_now_time": _iso(row.time_local.iloc[0]),
            "warning_m": None if pd.isna(warning) else round(float(warning), 2), "points": points}


MAX_AGE = timedelta(minutes=30)


def forecast_from_readings(bundle: dict, readings: pd.DataFrame, stations: pd.DataFrame, tide: pd.DataFrame | None,
                           graph_id: str, at: datetime) -> dict | None:
    """Serve-time forecast for one station from raw readings: None unless its latest level is at most 30 min old.
    Only readings up to that level are used, restricted to the rain gauges the model trained on."""
    at = pd.Timestamp(at)
    mine = readings[(readings.graph_id == graph_id) & (readings.kind == "wl") & readings.wl_m.notna()
                    & (readings.time_local <= at)]
    if mine.empty:
        return None
    last = mine.time_local.max().floor("15min")
    if at - last > MAX_AGE:
        return None
    window = readings[readings.time_local <= last]
    if bundle.get("rain_ids") is not None:
        window = window[(window.kind == "wl") | window.graph_id.isin(bundle["rain_ids"])]
    feats = dataset.build_features(window, stations, tide, [graph_id])
    return river_forecast(bundle, feats, graph_id, last.to_pydatetime())


def pick_station(readings: pd.DataFrame, stations: pd.DataFrame, wl_ids: list[str], at: datetime) -> str | None:
    """Stand-in until streets have their own station: among `wl_ids` with a level at most 30 min old, the one
    closest to its own warning level (smallest warning - level), ties by the larger rise over the last hour."""
    at = pd.Timestamp(at)
    warn = stations[stations.kind == "wl"].drop_duplicates("graph_id").set_index("graph_id").wl_warning_m
    wl = readings[(readings.kind == "wl") & readings.wl_m.notna() & (readings.time_local <= at)]
    best, best_key = None, None
    for gid in wl_ids:
        g = wl[wl.graph_id == gid].sort_values("time_local")
        if g.empty or at - g.time_local.iloc[-1] > MAX_AGE or gid not in warn.index or pd.isna(warn[gid]):
            continue
        level = float(g.wl_m.iloc[-1])
        ago = g[g.time_local <= g.time_local.iloc[-1] - timedelta(hours=1)]
        rise = level - float(ago.wl_m.iloc[-1]) if len(ago) else 0.0
        key = (round(float(warn[gid]) - level, 6), -rise)
        if best_key is None or key < best_key:
            best, best_key = gid, key
    return best


class BundleCache:
    """Loads forecast bundles lazily (`bundle_for`), caches them, and retries a missing one after `retry_s`."""

    def __init__(self, models_dir: Path, retry_s: float = 300, clock=time.monotonic):
        self.models_dir, self.retry_s, self.clock = Path(models_dir), retry_s, clock
        self._items: dict = {}
        self._lock = threading.Lock()

    def get(self, when: datetime, live: bool) -> dict | None:
        key = "live" if live else int(dataset.fold_of(pd.Series([pd.Timestamp(when)]))[0])
        with self._lock:
            hit = self._items.get(key)
            if hit is not None and (hit[1] is not None or self.clock() - hit[0] < self.retry_s):
                return hit[1]
            bundle = bundle_for(self.models_dir, when, live)
            self._items[key] = (self.clock(), bundle)
            return bundle
