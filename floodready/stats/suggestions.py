"""Improvement suggestions SUG-1..SUG-7 per street (PRD ADM-6), computed from stored alerts, answers and station health.

What counts: only non-replay alerts (backfill and live), answers that are not `source='demo'`, and REAL sensor readings
(`simulated = 0`). A "confirmed flood" is an alert whose outcome is confirmed by residents or a real sensor (recomputed
here so demo answers cannot leak in) or by a labelled news event (`events`). Nothing is guessed: a rule that lacks its
inputs (no rain source, no tide, no streets table) produces nothing. Priorities are derived (the PRD table has none):
SUG-1/2/6 high, SUG-3/4/5 medium, SUG-7 low. Every text ends with `DISCLAIMER`.
"""
from __future__ import annotations

import hashlib
import json
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from sqlalchemy import select

from .. import tide as tide_mod
from ..db import repo, schema
from . import episodes as episodes_mod
from . import outcomes

DISCLAIMER = "Screening suggestion; site survey needed."
PRIORITY = {"SUG-1": "high", "SUG-2": "high", "SUG-6": "high", "SUG-3": "medium", "SUG-4": "medium",
            "SUG-5": "medium", "SUG-7": "low"}
JPS_GUIDE_MM = 60.0               # "convective rain more than 60 mm in 2-4 hours may cause flash floods"
MIN_FLOODS_SUG1, MIN_FLOODS_SUG2, TIDE_SHARE, TIDE_WINDOW_H = 3, 2, 0.7, 2.0
NEIGHBOUR_M, NEIGHBOUR_MIN, ADJACENT_M = 500.0, 3, 30.0
CLUSTER_MIN, REPEAT_MIN, HIGH_SUSCEPTIBILITY = 3, 2, 4
READINESS_MIN, MISSED_MIN, STALE_MAX = 5, 2, 0.10
FLOOD_GAP = timedelta(hours=6)    # confirmed alerts on a street closer than this are one flood
GEO = Path(__file__).resolve().parents[2] / "assets" / "geo"
SLOT_MIN = 15

def _sug5_top_n() -> int:
    import yaml
    with open(GEO.parents[1] / "config" / "rules.yaml", encoding="utf-8") as f:
        return int(yaml.safe_load(f)["suggestions"]["sug5_top_n"])


OnsetRain = Callable[[str, datetime], "float | None"]


# ---------- station health ----------

def station_health(readings: pd.DataFrame, date_from: date, date_to: date, names: dict[str, str] | None = None) -> list[dict]:
    """[{graph_id, name, stale_pct}] (stale_pct is a 0-1 fraction) over [date_from, date_to] inclusive, worst first.

    `readings`: graph_id, kind ('rf'|'wl'), time_local, rain_15min_mm, wl_m, AFTER QC (floodready.qc), so a reading the
    QC blanked (including a gauge in dead state) is NaN. A 15-minute slot is stale when its series has no valid value
    in it (blanked, NaN or no row). A station with rain and river series reports its worse series."""
    if readings is None or readings.empty:
        return []
    start = pd.Timestamp(date_from)
    end = pd.Timestamp(date_to) + pd.Timedelta(days=1)
    slots = int((end - start) / pd.Timedelta(minutes=SLOT_MIN))
    df = readings[(readings["time_local"] >= start) & (readings["time_local"] < end)]
    names = names or {}
    worst: dict[str, float] = {}
    for (gid, kind), part in readings.groupby(["graph_id", "kind"]):
        col = "rain_15min_mm" if kind == "rf" else "wl_m"
        sub = df[(df["graph_id"] == gid) & (df["kind"] == kind) & df[col].notna()]
        valid = sub["time_local"].dt.floor(f"{SLOT_MIN}min").nunique()
        stale = round(1 - min(valid, slots) / slots, 3)
        worst[gid] = max(worst.get(gid, 0.0), stale)
    out = [{"graph_id": g, "name": names.get(g, g), "stale_pct": s} for g, s in worst.items()]
    return sorted(out, key=lambda h: (-h["stale_pct"], h["graph_id"]))


# ---------- helpers ----------

def _make_id(rule: str, key: str, date_from: date, date_to: date) -> str:
    period = f"{date_from:%y%m%d}-{date_to:%y%m%d}"
    sid = f"s_{rule.lower().replace('-', '')}_{key}_{period}"
    if len(sid) > 40:
        sid = f"s_{rule.lower().replace('-', '')}_{hashlib.sha1(key.encode()).hexdigest()[:10]}_{period}"
    return sid


def _suggestion(rule: str, key: str, street_id: str, street_name: str, text: str, evidence: dict,
                date_from: date, date_to: date) -> dict:
    return {"id": _make_id(rule, key, date_from, date_to), "street_id": street_id, "street_name": street_name,
            "rule": rule, "priority": PRIORITY[rule], "text": f"{text} {DISCLAIMER}", "evidence": evidence,
            "status": "open", "note": None}


def _load_streets():
    import geopandas as gpd
    frames = [gpd.read_file(p) for p in sorted(GEO.glob("*_streets.geojson"))]
    return pd.concat(frames, ignore_index=True) if frames else None


def _iso(d) -> str:
    return pd.Timestamp(d).date().isoformat()


def _names(streets) -> tuple[dict[str, str], dict[str, int]]:
    if streets is None or len(streets) == 0:
        return {}, {}
    return (dict(zip(streets["street_id"], streets["name"].fillna(streets["street_id"]))),
            {sid: int(s) for sid, s in zip(streets["street_id"], streets["susceptibility"]) if pd.notna(s)})


def _confirmed(conn, alerts: list[dict], events) -> set[str]:
    """alert_ids confirmed by non-demo resident answers, a REAL sensor, or a labelled news event."""
    rows = [a for a in alerts if a["kind"] == "alert"]
    answers: dict[str, list[dict]] = defaultdict(list)
    for r in repo.list_answers(conn):
        if r["alert_id"] and r["source"] != "demo":
            answers[r["alert_id"]].append(r)
    devices, threshold = repo.sensor_devices(), repo.sensor_threshold_cm()
    real = [{"device_id": r.device_id, "time_local": r.time_local, "level_cm": r.level_cm}
            for r in conn.execute(select(schema.sensor_readings).where(
                schema.sensor_readings.c.simulated.is_(False), schema.sensor_readings.c.level_cm > threshold))]
    out = set()
    for a in rows:
        mine = {d for d, streets in devices.items() if a["street_id"] in streets}
        hit = outcomes.sensor_above([r for r in real if r["device_id"] in mine], a["issued_at"], threshold)
        if outcomes.alert_outcome(answers.get(a["alert_id"], []), hit, issued_at=a["issued_at"]) == "confirmed":
            out.add(a["alert_id"])
    if events is not None:
        out |= set(outcomes.news_outcomes(events, rows))
    return out


def _floods(alerts: list[dict], confirmed: set[str]) -> dict[str, list[datetime]]:
    """street -> flood onsets (first confirmed alert of each cluster of confirmed alerts less than 6 h apart), sorted."""
    times: dict[str, list[datetime]] = defaultdict(list)
    for a in alerts:
        if a["alert_id"] in confirmed:
            times[a["street_id"]].append(outcomes._dt(a["issued_at"]))
    out = {}
    for street, ts in times.items():
        ts.sort()
        onsets = []
        for t in ts:
            if not onsets or t - last >= FLOOD_GAP:
                onsets.append(t)
            last = t
        out[street] = onsets
    return out


def _in(ts: datetime, start: datetime, end: datetime) -> bool:
    return start <= ts < end


def _neighbours(streets, sid: str, susc: dict[str, int]) -> list[str]:
    """Other streets within 500 m (centroid distance) whose susceptibility differs by at most 1."""
    if streets is None or sid not in susc or not {"centroid_lat", "centroid_lon"} <= set(streets.columns):
        return []
    me = streets[streets["street_id"] == sid].iloc[0]
    kx = 111_320 * np.cos(np.radians(me["centroid_lat"]))
    dx = (streets["centroid_lon"].to_numpy() - me["centroid_lon"]) * kx
    dy = (streets["centroid_lat"].to_numpy() - me["centroid_lat"]) * 111_320
    near = streets[(np.hypot(dx, dy) <= NEIGHBOUR_M) & (streets["street_id"] != sid).to_numpy()]
    return [n for n in near["street_id"] if n in susc and abs(susc[n] - susc[sid]) <= 1]


def _clusters(streets, candidates: list[str]) -> list[list[str]]:
    """Connected groups of candidate streets whose geometries are within 30 m of each other."""
    import geopandas as gpd
    sub = streets[streets["street_id"].isin(candidates)]
    if len(sub) < CLUSTER_MIN:
        return []
    geoms = gpd.GeoSeries(sub.geometry.to_numpy(), crs=streets.crs or "EPSG:4326").to_crs("EPSG:3375")
    ids = list(sub["street_id"])
    parent = list(range(len(ids)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            if geoms.iloc[i].distance(geoms.iloc[j]) <= ADJACENT_M:
                parent[find(i)] = find(j)
    groups: dict[int, list[str]] = defaultdict(list)
    for i, sid in enumerate(ids):
        groups[find(i)].append(sid)
    return [sorted(g) for g in groups.values() if len(g) >= CLUSTER_MIN]


# ---------- the rules ----------

def suggestions(conn, date_from: date, date_to: date, tide: pd.DataFrame | None, station_health: list[dict], *,
                streets=None, onset_rain: OnsetRain | None = None, events: pd.DataFrame | None = None, street_stations: dict | None = None,
                station_names: dict[str, str] | None = None, sug5_top_n: int | None = None) -> list[dict]:
    """SUG-1..SUG-7 for [date_from, date_to] inclusive, as Suggestion dicts (status 'open', note None), highest priority first.

    tide: hourly table (time_local, tide_height_m, hours_to_high_tide) or None (SUG-2 then yields nothing).
    station_health: [{graph_id, name, stale_pct}] (see `station_health`).
    streets: GeoDataFrame (street_id, name, susceptibility, centroid_lat/lon, geometry); default assets/geo/*_streets.geojson.
    onset_rain(street_id, onset) -> mm of rain in the 2-4 h before the flood onset, or None; without it SUG-1 yields nothing.
    street_stations/station_names: street -> {wl: river station} mapping and graph_id -> name (SUG-5 evidence).
    sug5_top_n: SUG-5 cap, default `suggestions.sug5_top_n` of config/rules.yaml.
    events: labelled news events (floodready.stats.outcomes.news_outcomes); omitted = residents and sensors only."""
    if streets is None:
        streets = _load_streets()
    name_of, susc = _names(streets)
    start, end = datetime.combine(date_from, datetime.min.time()), datetime.combine(date_to + timedelta(days=1), datetime.min.time())
    prev_start, prev_end = (pd.Timestamp(start) - pd.DateOffset(years=1)).to_pydatetime(), (pd.Timestamp(end) - pd.DateOffset(years=1)).to_pydatetime()
    alerts = repo.list_alerts(conn, include_replay=False, include_backfill=True, count_simulated_sensor=False,
                              since=prev_start)
    for a in alerts:
        a["issued_at"] = outcomes._dt(a["issued_at"]).isoformat()
    confirmed = _confirmed(conn, alerts, events)
    all_floods = _floods(alerts, confirmed)
    floods = {s: [t for t in ts if _in(t, start, end)] for s, ts in all_floods.items()}
    floods = {s: ts for s, ts in floods.items() if ts}
    last_year = {s: [t for t in ts if _in(t, prev_start, prev_end)] for s, ts in all_floods.items()}
    out: list[dict] = []

    def name(sid: str) -> str:
        return name_of.get(sid, sid)

    def add(rule, key, sid, text, evidence, sname=None):
        out.append(_suggestion(rule, key, sid, sname or name(sid), text, evidence, date_from, date_to))

    for sid, onsets in sorted(floods.items()):
        dates = [_iso(t) for t in onsets]
        # SUG-1 drainage capacity
        if onset_rain is not None:
            rains = [(t, onset_rain(sid, t)) for t in onsets]
            known = [(t, r) for t, r in rains if r is not None]
            if len(known) >= MIN_FLOODS_SUG1 and statistics.median(r for _, r in known) < JPS_GUIDE_MM:
                med = statistics.median(r for _, r in known)
                nbr = _neighbours(streets, sid, susc)
                ev = {"flood_dates": [_iso(t) for t, _ in known], "rain_at_onset_mm": [round(float(r), 1) for _, r in known],
                      "median_rain_mm": round(float(med), 1), "jps_guide_mm": JPS_GUIDE_MM,
                      "notes": f"Median rain at flood onset {med:.0f} mm (3 h sum at the street's gauges) is below the JPS guide of {JPS_GUIDE_MM:.0f} mm in 2-4 h."}
                if nbr:
                    ev["neighbour_streets"] = len(nbr)
                    ev["neighbour_floods"] = sum(len(floods.get(n, [])) for n in nbr)
                add("SUG-1", sid, sid, f"{name(sid)} needs a drainage capacity review / upgrade: it floods with less rain than the JPS guide.", ev)
        # SUG-2 tidal backflow
        if tide is not None and len(onsets) >= MIN_FLOODS_SUG2:
            hrs = tide_mod.tide_at(tide, pd.DatetimeIndex(onsets))["hours_to_high_tide"].to_numpy()
            ok = ~np.isnan(hrs)
            if ok.sum() >= MIN_FLOODS_SUG2:
                share = float((np.abs(hrs[ok]) <= TIDE_WINDOW_H).mean())
                if share >= TIDE_SHARE:
                    add("SUG-2", sid, sid, f"Check outfall flap gates / backflow valves draining {name(sid)}.",
                        {"flood_dates": [d for d, k in zip(dates, ok) if k],
                         "hours_to_high_tide": [round(float(h), 1) for h in hrs[ok]], "share_near_high_tide": round(share, 2),
                         "notes": f"{share:.0%} of {int(ok.sum())} floods began within {TIDE_WINDOW_H:.0f} h of high tide."})
        # SUG-3 blockage / maintenance
        prev = len(last_year.get(sid, []))
        nbr = _neighbours(streets, sid, susc)
        quiet = [n for n in nbr if not floods.get(n)]
        if len(onsets) >= REPEAT_MIN and len(nbr) >= NEIGHBOUR_MIN and len(quiet) == len(nbr):
            add("SUG-3", sid + "~nbr", sid, f"Inspect and clear drains and culverts on {name(sid)} before the monsoon.",
                {"flood_dates": dates, "neighbours_without_floods": len(quiet),
                 "notes": f"{name(sid)} flooded {len(onsets)} times while all {len(nbr)} neighbours within {NEIGHBOUR_M:.0f} m of similar susceptibility did not."})
        if prev >= 1 and len(onsets) >= REPEAT_MIN and len(onsets) >= 2 * prev:
            add("SUG-3", sid + "~yoy", sid, f"Inspect and clear drains and culverts on {name(sid)} before the monsoon.",
                {"flood_dates": dates, "floods_this_period": len(onsets), "floods_same_period_last_year": prev,
                 "notes": f"{len(onsets)} floods this period against {prev} in the same period a year earlier."})

    # SUG-4 storage / retention
    if streets is not None and floods:
        cand = [s for s, ts in floods.items() if len(ts) >= REPEAT_MIN and susc.get(s, 0) >= HIGH_SUSCEPTIBILITY]
        for group in _clusters(streets, cand):
            days = sum(len({t.date() for t in floods[s]}) for s in group)
            names = [name(s) for s in group]
            label = ", ".join(names[:3]) + (f" and {len(names) - 3} more" if len(names) > 3 else "")
            add("SUG-4", group[0], group[0], f"Area around {label} is a candidate for retention / on-site storage.",
                {"street_ids": group, "flood_dates": sorted({_iso(t) for s in group for t in floods[s]}),
                 "total_flood_days": days,
                 "notes": f"{len(group)} adjacent high-susceptibility streets with repeated confirmed floods. Homes nearby: not available."},
                sname=names[0])

    # SUG-5 pre-event readiness: count alert EPISODES (flapping merged, see stats/episodes.py), not raw alert rows
    ready: dict[str, list[dict]] = defaultdict(list)
    for e in episodes_mod.episodes(alerts):
        if e["level"] in ("warning", "danger") and _in(e["start"], start, end):
            ready[e["street_id"]].append(e)
    eligible = {sid: eps for sid, eps in ready.items() if len(eps) >= READINESS_MIN}
    ranked = sorted(eligible, key=lambda sid: (-len(eligible[sid]), -sum(e["level"] == "danger" for e in eligible[sid]),
                                               -susc.get(sid, 0), sid))
    wl_of = {sid: ((street_stations or {}).get(sid) or {}).get("wl") for sid in ranked}
    for rank, sid in enumerate(ranked[:sug5_top_n if sug5_top_n is not None else _sug5_top_n()], start=1):
        eps = eligible[sid]
        wl = wl_of[sid]
        shared = sum(1 for o in ranked if wl and wl_of[o] == wl)
        ev = {"alert_count": len(eps), "episodes": len(eps), "danger_episodes": sum(e["level"] == "danger" for e in eps),
              "raw_alert_rows": sum(e["rows"] for e in eps), "rank": rank, "eligible_streets": len(ranked),
              "flood_dates": sorted(_iso(e["start"]) for e in eps),
              "notes": f"Rank {rank} of {len(ranked)} eligible streets (at least {READINESS_MIN} Warning/Danger episodes; ranked by episodes, Danger episodes, susceptibility). "
                       f"{len(eps)} separate alert episodes in the period (flapping merged); dates are episode starts, not confirmed floods."}
        if wl:
            wl_name = (station_names or {}).get(wl, wl)
            ev.update({"river_station": wl, "river_station_name": wl_name, "eligible_streets_on_same_river_station": shared})
            ev["notes"] += f" The count is driven by river station {wl_name}, shared by {shared} of the eligible streets."
        add("SUG-5", sid, sid, f"Add {name(sid)} to the pre-storm drain-clearing and staff deployment list.", ev)

    # SUG-6 monitoring gap
    reports = [r for r in repo.list_answers(conn) if r["answer"] == "report" and _in(outcomes._dt(r["answered_at"]), start, end)]
    missed: dict[str, list[dict]] = defaultdict(list)
    for m in outcomes.missed_floods(reports, alerts):
        missed[m["street_id"]].append(m)
    for sid, ms in sorted(missed.items()):
        if len(ms) >= MISSED_MIN:
            add("SUG-6", sid, sid, f"Our model under-predicts {name(sid)}: add a sensor or review its susceptibility score.",
                {"missed_floods": len(ms), "flood_dates": [_iso(m["first_reported_at"]) for m in ms],
                 "notes": f"{len(ms)} resident-reported floods with no Warning or Danger in the previous 3 h."})

    # SUG-7 data health
    for h in station_health:
        if h["stale_pct"] > STALE_MAX:
            add("SUG-7", h["graph_id"], f"station:{h['graph_id']}",
                f"JPS station {h['name']} is often offline ({h['stale_pct']:.0%} of the period without valid data); consider a backup station or our own rain gauge.",
                {"graph_id": h["graph_id"], "stale_pct": h["stale_pct"],
                 "stale_hours": round(((date_to - date_from).days + 1) * 24 * h["stale_pct"], 1),
                 "notes": "Stale = no valid reading in the 15-minute slot (missing, or blanked by QC including dead-gauge time)."},
                sname=h["name"])

    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(out, key=lambda s: (order[s["priority"]], s["rule"], s["id"]))


def save(conn, items: list[dict], date_from: date, date_to: date) -> int:
    """Upsert into the suggestions table. status/note are NOT written, so an existing row keeps its admin decision."""
    rows = []
    for s in items:
        row = {k: v for k, v in s.items() if k not in ("status", "note", "street_name")}
        row["period_from"], row["period_to"] = date_from, date_to
        rows.append(row)
    repo.upsert_suggestions(conn, rows)
    return len(rows)
