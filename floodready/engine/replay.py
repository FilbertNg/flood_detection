"""Replay an event (or any period) through the engine step by step (build plan task E6).

The same code path as the live tick: features → trigger (rules floor, ML once
wired in) → street states → alerts. Features are computed once for the whole
period (vectorised) and read per step, using only data up to each step.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator

import pandas as pd

from .. import qc
from . import alerts as alerts_mod
from . import levels, rules
from .features import compute_station_features
from .types import Alert, StreetState, TriggerResult



@dataclass(frozen=True)
class ReplayStep:
    time: datetime
    trigger: TriggerResult
    states: list[StreetState]
    alerts: list[Alert]


def run(start: datetime, end: datetime, step: timedelta, readings: pd.DataFrame, stations: pd.DataFrame,
        streets: pd.DataFrame, station_ids: list[str], rules_cfg: dict, matrix_table: dict,
        ml_bundle: dict | None = None, ml_cfg: dict | None = None, wl_ids: list[str] | None = None,
        tide: pd.DataFrame | None = None) -> Iterator[ReplayStep]:
    """Rules floor always; with `ml_bundle` ({model, features}), `ml_cfg` and the township's river
    stations `wl_ids`, the ML trigger is combined in (levels.combine) and its probability is shown."""
    window = readings[(readings.time_local > pd.Timestamp(start) - timedelta(hours=26)) &
                      (readings.time_local <= pd.Timestamp(end))]
    all_features = compute_station_features(window[window.graph_id.isin(station_ids)], stations, end=end,
                                            stale_after_min=rules_cfg.get("stale_after_min", 120))
    by_time = {t: f for t, f in all_features.groupby("time_local")}
    empty = all_features.iloc[0:0]

    ml_feats = None
    if ml_bundle is not None and ml_cfg is not None and wl_ids:
        from ..ml import dataset
        ml_window = readings[(readings.time_local > pd.Timestamp(start) - timedelta(days=5)) &
                             (readings.time_local <= pd.Timestamp(end))]
        ml_feats = dataset.build_features(ml_window, stations, tide, wl_ids)
        names = stations[stations.kind == "wl"].set_index("graph_id")["name"]
        ml_feats["name"] = ml_feats.graph_id.map(names).fillna(ml_feats.graph_id)

    prev: dict[str, StreetState] = {}
    last_alerts: dict[str, Alert] = {}
    t = pd.Timestamp(start)
    while t <= pd.Timestamp(end):
        feats = by_time.get(t, empty)
        trigger = rules.township_trigger(feats, station_ids, rules_cfg)
        if pd.isna(pd.Timestamp(trigger.data_time)) or trigger.data_time == datetime.min:
            trigger = TriggerResult(level=trigger.level, confidence=trigger.confidence, fired_by=trigger.fired_by,
                                    reasons=trigger.reasons, data_time=t.to_pydatetime(),
                                    stale_stations=trigger.stale_stations)
        ml = None
        if ml_feats is not None:
            from ..ml import predict
            ml = predict.township_probability(ml_bundle["model"], ml_bundle["features"], ml_feats, wl_ids,
                                              t.to_pydatetime(), ml_cfg)
            trigger = levels.combine(trigger, ml, ml_cfg)
        states = levels.street_states(streets, trigger, rules_cfg, matrix_table,
                                      flood_probability=ml.p if ml is not None else None)
        issued = alerts_mod.issue(prev, states, last_alerts, rules_cfg)
        prev = {s.street_id: s for s in states}
        for alert in issued:
            last_alerts[alert.street_id] = alert
        yield ReplayStep(time=t.to_pydatetime(), trigger=trigger, states=states, alerts=issued)
        t += step


def load_archive_readings(hist_dir: Path, station_ids: list[str], start: datetime, end: datetime) -> pd.DataFrame:
    """Readings for the given stations from the JPS history archive (data/raw/jps_hist), after QC (floodready.qc)."""
    frames = []
    for kind, value in (("rf", "rain_15min_mm"), ("wl", "wl_m")):
        for graph_id in station_ids:
            path = Path(hist_dir) / kind / f"{graph_id}.parquet"
            if not path.exists():
                continue
            df = pd.read_parquet(path)
            frames.append(pd.DataFrame({"graph_id": graph_id, "kind": kind, "time_local": df.time_local,
                                        "rain_15min_mm": df[value] if kind == "rf" else float("nan"),
                                        "wl_m": df[value] if kind == "wl" else float("nan")}))
    if not frames:
        return pd.DataFrame(columns=["graph_id", "kind", "time_local", "rain_15min_mm", "wl_m"])
    # QC runs on each gauge's full history (gap and stuck rules need context), then the window is cut
    clean, _ = qc.clean_readings(pd.concat(frames, ignore_index=True))
    in_window = (clean.time_local >= pd.Timestamp(start)) & (clean.time_local <= pd.Timestamp(end))
    return clean[in_window].reset_index(drop=True)
