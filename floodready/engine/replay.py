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


def _dated(trigger: TriggerResult, t: pd.Timestamp) -> TriggerResult:
    """A trigger with no readings at all carries no data time: stamp it with the step time."""
    if pd.isna(pd.Timestamp(trigger.data_time)) or trigger.data_time == datetime.min:
        return TriggerResult(level=trigger.level, confidence=trigger.confidence, fired_by=trigger.fired_by,
                             reasons=trigger.reasons, data_time=t.to_pydatetime(), stale_stations=trigger.stale_stations)
    return trigger


def _own_features(feats: pd.DataFrame, wl: str | None, rf: tuple[str, ...]) -> pd.DataFrame:
    """The street's own station rows: its river station's level row and its rain gauges' rain rows."""
    return feats[((feats.kind == "wl") & (feats.graph_id == wl)) | ((feats.kind == "rf") & feats.graph_id.isin(rf))]


def run(start: datetime, end: datetime, step: timedelta, readings: pd.DataFrame, stations: pd.DataFrame,
        streets: pd.DataFrame, station_ids: list[str], rules_cfg: dict, matrix_table: dict,
        ml_bundle: dict | None = None, ml_cfg: dict | None = None, wl_ids: list[str] | None = None,
        tide: pd.DataFrame | None = None, street_stations: dict | None = None) -> Iterator[ReplayStep]:
    """Rules floor always; with `ml_bundle` ({model, features}), `ml_cfg` and the township's river
    stations `wl_ids`, the ML trigger is combined in (levels.combine) and its probability is shown.

    `street_stations` ({street_id: {"wl", "rf", ...}}, see engine/street_stations.py): each street's trigger
    comes from its own stations only (cached per station group) and its ML result from its own river station.
    Without it, or for a street missing from it, the street gets the township-wide trigger. `step.trigger`
    stays the township-wide summary."""
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

    # (street_id, susceptibility, station group or None for the township-wide trigger)
    rows = []
    for street_id, susceptibility in zip(streets["street_id"], streets["susceptibility"]):
        entry = (street_stations or {}).get(street_id)
        group = (entry.get("wl") or None, tuple(entry.get("rf", ()))) if entry is not None else None
        rows.append((street_id, int(susceptibility), group))

    prev: dict[str, StreetState] = {}
    last_alerts: dict[str, Alert] = {}
    t = pd.Timestamp(start)
    while t <= pd.Timestamp(end):
        feats = by_time.get(t, empty)
        trigger = _dated(rules.township_trigger(feats, station_ids, rules_cfg), t)
        ml, ml_by_station = None, {}
        if ml_feats is not None:
            from ..ml import predict
            ml_by_station = predict.station_probabilities(ml_bundle["model"], ml_bundle["features"], ml_feats, wl_ids,
                                                          t.to_pydatetime(), ml_cfg)
            ml = max(ml_by_station.values(), key=lambda r: r.p) if ml_by_station else None
            trigger = levels.combine(trigger, ml, ml_cfg)

        group_triggers: dict[tuple, tuple[TriggerResult, float | None]] = {}
        states = []
        for street_id, susceptibility, group in rows:
            if group is None:
                street_trigger, p = trigger, ml.p if ml is not None else None
            else:
                if group not in group_triggers:
                    wl, rf = group
                    own = _dated(rules.township_trigger(_own_features(feats, wl, rf),
                                                        ([wl] if wl else []) + list(rf), rules_cfg), t)
                    own_ml = ml_by_station.get(wl) if wl else None
                    group_triggers[group] = (levels.combine(own, own_ml, ml_cfg) if own_ml is not None else own,
                                             own_ml.p if own_ml is not None else None)
                street_trigger, p = group_triggers[group]
            states.append(levels.street_state(street_id, susceptibility, street_trigger, rules_cfg, matrix_table,
                                              flood_probability=p))
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
