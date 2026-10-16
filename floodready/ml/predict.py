"""ML trigger inference (build plan task ML4).

Per-station probability (and the township summary = max over its river stations) of the model's
probability that the river crosses its warning level within the horizon,
smoothed as the max over the last `smoothing_min` minutes.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from ..engine.types import Level, MLResult, Reason

log = logging.getLogger(__name__)


def load_or_none(path: Path) -> dict | None:
    """The saved bundle {model, features, ...}, or None if it can't be loaded (engine falls back to rules)."""
    try:
        import joblib
        return joblib.load(path)
    except Exception as exc:  # missing file, version mismatch...
        log.warning("ML model unavailable (%s): rules only", exc)
        return None


def bundle_for(models_dir: Path, when: datetime, live: bool, name: str = "trigger_v1") -> dict | None:
    """The model to use at `when`. Live: the final model. Replaying the past: the fold model that was
    trained WITHOUT that period, so a replay never shows an in-sample (leaked) probability."""
    from .dataset import fold_of
    models_dir = Path(models_dir)
    if not live:
        fold = int(fold_of(pd.Series([pd.Timestamp(when)]))[0])
        bundle = load_or_none(models_dir / f"{name}_oof{fold}.joblib")
        if bundle is not None:
            return {**bundle, "out_of_sample": True}
    bundle = load_or_none(models_dir / f"{name}.joblib")
    return {**bundle, "out_of_sample": False} if bundle is not None else None


def ml_result(p: float, station: str, cfg: dict) -> MLResult:
    level = Level.WARNING if p >= cfg["p_warning"] else Level.WATCH if p >= cfg["p_watch"] else Level.NORMAL
    pct, h = round(p * 100), cfg.get("horizon_h", 2)
    reason = Reason(code="ml_probability", value=round(p, 3), unit="p", station=station,
                    text_en=f"{pct}% chance the river at {station} crosses warning level within {h} h",
                    text_ms=f"{pct}% kemungkinan paras {station} melepasi paras amaran dalam {h} jam")
    return MLResult(p=p, level=level, station=station, horizon_h=h, reasons=(reason,))


def station_probabilities(model, features: list[str], feats: pd.DataFrame, wl_station_ids: list[str],
                          at: datetime, cfg: dict) -> dict[str, MLResult]:
    """One result per river station that has feature rows: its probability, smoothed as the max over the last
    `smoothing_min` minutes. `feats`: ML feature rows (graph_id, name, time_local, features...)."""
    window_start = pd.Timestamp(at) - timedelta(minutes=cfg.get("smoothing_min", 30))
    rows = feats[feats.graph_id.isin(wl_station_ids) & (feats.time_local >= window_start) & (feats.time_local <= pd.Timestamp(at))]
    if rows.empty:
        return {}
    missing = [f for f in features if f not in rows.columns]
    if missing:  # bundle trained on another FEATURES list: rules only until the model is retrained
        log.warning("ML model expects %d features the pipeline no longer builds (%s): rules only; retrain the model",
                    len(missing), ", ".join(missing[:5]) + ("…" if len(missing) > 5 else ""))
        return {}
    rows = rows.assign(_p=model.predict_proba(rows[features])[:, 1])
    results = {}
    for graph_id, group in rows.groupby("graph_id", sort=False):
        best = group.iloc[int(group["_p"].to_numpy().argmax())]
        results[str(graph_id)] = ml_result(float(best["_p"]), str(best["name"]), cfg)
    return results


def township_probability(model, features: list[str], feats: pd.DataFrame, wl_station_ids: list[str],
                         at: datetime, cfg: dict) -> MLResult | None:
    """Township summary: the highest station probability (see station_probabilities)."""
    results = station_probabilities(model, features, feats, wl_station_ids, at, cfg)
    return max(results.values(), key=lambda r: r.p) if results else None
