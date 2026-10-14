"""Replay an event (or any period) through the engine step by step (build plan task E6).

The same code path as the live tick: features → trigger (rules floor, ML once
wired in) → street states → alerts. Features are computed once for the whole
period (vectorised) and read per step, using only data up to each step.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Iterator

import pandas as pd

from . import alerts as alerts_mod
from . import levels, rules
from .features import compute_station_features
from .types import Alert, StreetState, TriggerResult

# trigger_fn(features_at_t, time) -> TriggerResult; default: rules only.
TriggerFn = Callable[[pd.DataFrame, datetime], TriggerResult]


@dataclass(frozen=True)
class ReplayStep:
    time: datetime
    trigger: TriggerResult
    states: list[StreetState]
    alerts: list[Alert]


def run(start: datetime, end: datetime, step: timedelta, readings: pd.DataFrame, stations: pd.DataFrame,
        streets: pd.DataFrame, station_ids: list[str], rules_cfg: dict, matrix_table: dict,
        trigger_fn: TriggerFn | None = None) -> Iterator[ReplayStep]:
    window = readings[(readings.time_local > pd.Timestamp(start) - timedelta(hours=26)) &
                      (readings.time_local <= pd.Timestamp(end))]
    all_features = compute_station_features(window[window.graph_id.isin(station_ids)], stations, end=end,
                                            stale_after_min=rules_cfg.get("stale_after_min", 120))
    by_time = {t: f for t, f in all_features.groupby("time_local")}
    empty = all_features.iloc[0:0]
    if trigger_fn is None:
        def trigger_fn(feats, _t):
            return rules.township_trigger(feats, station_ids, rules_cfg)

    prev: dict[str, StreetState] = {}
    last_alerts: dict[str, Alert] = {}
    t = pd.Timestamp(start)
    while t <= pd.Timestamp(end):
        feats = by_time.get(t, empty)
        trigger = trigger_fn(feats, t.to_pydatetime())
        if pd.isna(pd.Timestamp(trigger.data_time)) or trigger.data_time == datetime.min:
            trigger = TriggerResult(level=trigger.level, confidence=trigger.confidence, fired_by=trigger.fired_by,
                                    reasons=trigger.reasons, data_time=t.to_pydatetime(),
                                    stale_stations=trigger.stale_stations)
        states = levels.street_states(streets, trigger, rules_cfg, matrix_table)
        issued = alerts_mod.issue(prev, states, last_alerts, rules_cfg)
        prev = {s.street_id: s for s in states}
        for alert in issued:
            last_alerts[alert.street_id] = alert
        yield ReplayStep(time=t.to_pydatetime(), trigger=trigger, states=states, alerts=issued)
        t += step


def load_archive_readings(hist_dir: Path, station_ids: list[str], start: datetime, end: datetime) -> pd.DataFrame:
    """Readings for the given stations from the JPS history archive (data/raw/jps_hist)."""
    frames = []
    for kind, value in (("rf", "rain_15min_mm"), ("wl", "wl_m")):
        for graph_id in station_ids:
            path = Path(hist_dir) / kind / f"{graph_id}.parquet"
            if not path.exists():
                continue
            df = pd.read_parquet(path)
            df = df[(df.time_local >= pd.Timestamp(start)) & (df.time_local <= pd.Timestamp(end))]
            frames.append(pd.DataFrame({"graph_id": graph_id, "kind": kind, "time_local": df.time_local,
                                        "rain_15min_mm": df[value] if kind == "rf" else float("nan"),
                                        "wl_m": df[value] if kind == "wl" else float("nan")}))
    if not frames:
        return pd.DataFrame(columns=["graph_id", "kind", "time_local", "rain_15min_mm", "wl_m"])
    return pd.concat(frames, ignore_index=True)
