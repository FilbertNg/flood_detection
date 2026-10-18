"""Engine records -> API contract shapes (docs/api-contract.md, packages/shared/src/api/types.ts)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pandas as pd

from ..engine import features, street_stations
from ..engine.types import Reason, StreetState
from ..jobs import now_myt
from ..ml import forecast as river
from .runner import EngineContext, Snapshot, iso

log = logging.getLogger(__name__)


def reason(r: Reason) -> dict:
    return {"code": r.code, "value": r.value, "unit": r.unit, "station": r.station, "text": {"en": r.text_en, "ms": r.text_ms}}


def _states(snap: Snapshot) -> dict[str, StreetState]:
    return {s.street_id: s for s in snap.step.states} if snap.step else {}


def streets_geojson(ctx: EngineContext, snap: Snapshot) -> dict:
    states = _states(snap)
    updated = iso(snap.step.time) if snap.step else iso(datetime.now())
    features = []
    for row in ctx.streets.itertuples():
        state = states.get(row.street_id)
        features.append({
            "type": "Feature",
            "geometry": row.geometry.__geo_interface__,
            "properties": {"street_id": row.street_id, "name": row.name, "township_id": row.township_id,
                           "susceptibility": int(row.susceptibility),
                           "level": state.level.json if state else "normal", "updated_at": updated},
        })
    return {"type": "FeatureCollection", "features": features}


def _tide(ctx: EngineContext, start: datetime) -> list[dict]:
    table = ctx.tide_table()
    if table is None or not len(table):
        return []
    t = table[(table.time_local >= pd.Timestamp(start).floor("h")) &
              (table.time_local <= pd.Timestamp(start) + timedelta(hours=12))]
    return [{"time": iso(x), "height_m": round(float(h), 2)} for x, h in zip(t.time_local, t.tide_height_m) if pd.notna(h)]


def river_forecast_for(ctx: EngineContext, snap: Snapshot, at: datetime, graph_id: str | None = None) -> dict | None:
    """+1 h / +2 h level with a range. `graph_id`: the street's own station (WP5); until then None picks,
    among the township's river stations with a fresh level, the one closest to its warning level.
    Never raises: the forecast is informational and must not break the street page."""
    if ctx.river_forecast is None or snap.step is None or not len(snap.readings):
        return None
    try:
        if graph_id is None:
            wl_ids = [s["graph_id"] for s in ctx.township["stations"] if "WL" in s.get("types", [])]
            graph_id = river.pick_station(snap.readings, ctx.stations, wl_ids, at)
        if graph_id is None:
            return None
        out = ctx.river_forecast(snap.readings, graph_id, at, snap.mode == "live")
        if not out:
            return None
        names = ctx.stations[ctx.stations.kind == "wl"].drop_duplicates("graph_id").set_index("graph_id").name
        return {**out, "name": str(names.get(graph_id, graph_id))}
    except Exception:
        log.exception("river forecast failed")
        return None


def _street_river_forecast(ctx: EngineContext, snap: Snapshot, at: datetime, street_id: str) -> dict | None:
    """The forecast for the street's river station at `at`: its first candidate with a valid reading at or before
    `at` (the same choice the engine made for its rules and ML probability). A street whose candidates are all dead
    gets no forecast; it does not borrow a township-wide pick."""
    candidates = street_stations.candidates_for(ctx.street_stations, street_id)
    if not candidates:
        return river_forecast_for(ctx, snap, at, None)
    dead: set[str] = set()
    if snap.step is not None and len(snap.readings):
        wl = snap.readings[snap.readings.graph_id.isin(candidates) & (snap.readings.kind == "wl")]
        feats = features.station_features(wl, at, ctx.stations, ctx.rules_cfg.get("stale_after_min", 120))
        dead = street_stations.dead_wl(feats, candidates)
    chosen = street_stations.wl_for(ctx.street_stations, street_id, dead)
    return river_forecast_for(ctx, snap, at, chosen) if chosen else None


def street_detail(ctx: EngineContext, snap: Snapshot, street_id: str) -> dict | None:
    match = ctx.streets[ctx.streets.street_id == street_id]
    if match.empty:
        return None
    row = match.iloc[0]
    state = _states(snap).get(street_id)
    data_time = snap.step.time if snap.step else datetime.now()
    history = snap.alerts_for(street_id)
    still_elevated = state is None or state.level.json != "normal"      # a missed all-clear must not stay active
    # latest row per horizon: a nowcast all-clear never hides an outlook and the reverse; nowcast wins when both are active
    latest = {}
    for a in history:
        latest.setdefault(a.get("horizon", "nowcast"), a)
    now_row, out_row = latest.get("nowcast"), latest.get("outlook")
    pick = (now_row if now_row and now_row["kind"] == "alert" and still_elevated
            else out_row if out_row and out_row["kind"] == "alert" else None)
    active = {"alert_id": pick["alert_id"], "level": pick["level"], "issued_at": pick["issued_at"]} if pick else None
    rain_next = ctx.forecast(data_time) if (ctx.forecast is not None and snap.mode == "live") else []
    reasons = [reason(r) for r in state.reasons] if state else []
    if ctx.radar is not None and snap.mode == "live":
        try:
            radar_reason = ctx.radar(now_myt())   # informational: appended after, never part of the level
        except Exception:  # a bad radar frame must not break the street page
            log.exception("radar reason failed")
            radar_reason = None
        if radar_reason is not None:
            reasons.append(reason(radar_reason))
    return {
        "street_id": street_id, "name": row["name"], "township_id": row["township_id"],
        "susceptibility": int(row["susceptibility"]),
        "level": state.level.json if state else "normal",
        "trigger_level": state.trigger_level.json if state else "normal",
        "confidence": state.confidence if state else "low",
        "flood_probability": round(state.flood_probability, 3) if state and state.flood_probability is not None else None,
        "fired_by": list(state.fired_by) if state else [],
        "window": {"start": iso(state.window_start), "end": iso(state.window_end)} if state and state.window_start else None,
        "reasons": reasons,
        "data_time": iso(data_time),
        "rain_next_12h": rain_next,
        "tide": _tide(ctx, data_time),
        "river_forecast": _street_river_forecast(ctx, snap, data_time, street_id),
        "stations": list(street_stations.stations_for(ctx.street_stations, street_id)
                         or [s["graph_id"] for s in ctx.township["stations"]]),
        "active_alert": active,
        "history": history[:10],
        "is_replay": snap.mode == "replay",
    }


def stations(ctx: EngineContext, snap: Snapshot) -> list[dict]:
    ids = [s["graph_id"] for s in ctx.township["stations"]]
    now = pd.Timestamp(snap.step.time) if snap.step else pd.Timestamp(datetime.now())
    readings = snap.readings
    out = []
    lookup = ctx.stations[ctx.stations.graph_id.isin(ids)]
    for row in lookup.itertuples():
        mine = readings[(readings.graph_id == row.graph_id) & (readings.kind == row.kind) & (readings.time_local <= now)] \
            if len(readings) else readings
        col = "rain_15min_mm" if row.kind == "rf" else "wl_m"
        valid = mine.dropna(subset=[col]) if len(mine) else mine
        latest = None
        if len(valid):
            last_time = valid.time_local.max()
            if row.kind == "rf":
                hour = valid[valid.time_local > last_time - timedelta(hours=1)]
                latest = {"time": iso(last_time), "rain_1h_mm": round(float(hour[col].sum()), 1), "wl_m": None}
            else:
                latest = {"time": iso(last_time), "rain_1h_mm": None,
                          "wl_m": round(float(valid.loc[valid.time_local == last_time, col].iloc[-1]), 2)}
        stale = latest is None or (now - pd.Timestamp(valid.time_local.max())) > timedelta(hours=2)
        thresholds = ({"alert": row.wl_alert_m, "warning": row.wl_warning_m, "danger": row.wl_danger_m}
                      if row.kind == "wl" and pd.notna(row.wl_danger_m) else None)
        out.append({"graph_id": row.graph_id, "name": row.name, "kind": row.kind,
                    "lat": None if pd.isna(row.lat) else row.lat, "lon": None if pd.isna(row.lon) else row.lon,
                    "latest": latest, "thresholds": thresholds, "is_stale": bool(stale)})
    return out


def series(snap: Snapshot, graph_id: str, start: datetime | None, end: datetime | None) -> list[dict]:
    r = snap.readings
    if not len(r):
        return []
    r = r[r.graph_id == graph_id]
    if start is not None:
        r = r[r.time_local >= pd.Timestamp(start)]
    if end is not None:
        r = r[r.time_local <= pd.Timestamp(end)]
    rain = r[r.kind == "rf"].groupby("time_local").rain_15min_mm.last()
    level = r[r.kind == "wl"].groupby("time_local").wl_m.last()
    merged = pd.concat([rain, level], axis=1).sort_index()
    return [{"time": iso(t), "rain_15min_mm": None if pd.isna(a) else float(a), "wl_m": None if pd.isna(b) else float(b)}
            for t, a, b in zip(merged.index, merged.get("rain_15min_mm", pd.Series(dtype=float)).reindex(merged.index),
                               merged.get("wl_m", pd.Series(dtype=float)).reindex(merged.index))]


def status(snap: Snapshot, ctx: EngineContext) -> dict:
    now = datetime.now()
    station_rows = stations(ctx, snap)
    return {
        "mode": snap.mode,
        "now": iso(now),
        "data_time": iso(snap.step.time) if snap.step else iso(now),
        "replay": {"event": snap.replay["event"], "speed": snap.replay["speed"]} if snap.replay else None,
        "sources": {"jps_wl_stale": sum(1 for s in station_rows if s["kind"] == "wl" and s["is_stale"]),
                    "jps_rf_stale": sum(1 for s in station_rows if s["kind"] == "rf" and s["is_stale"])},
    }
