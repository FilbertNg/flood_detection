"""Improvement suggestions SUG-1..SUG-7 per street (PRD ADM-6), computed from stored alerts, answers and station health.

What counts: only NOWCAST alerts that are not replay (backfill and live; Outlook rows are a different horizon and never
count), answers that are not `source='demo'`, and REAL sensor readings (`simulated = 0`). A "confirmed flood" is an
alert whose outcome is confirmed by residents or a real sensor (recomputed here so demo answers cannot leak in) or by a
CHECKED labelled news event (`events`, read through `stats.events.normalise`). Nothing is guessed: a rule that lacks its
inputs (no rain source, no tide, no streets table) produces nothing.

Priority (PRD line 195): SUG-1..4 are high when a confirming answer reports knee depth or above, or the news row names
homes affected, otherwise medium (road-only flooding); SUG-5 is medium; SUG-6 and SUG-7 (data and monitoring) are low.
Every text ends with `DISCLAIMER`.

Flood onset (SUG-1): the earliest OBSERVATION in a flood: the first usable resident "yes", the first real sensor reading
above threshold, or the news onset (never the alert time, which comes before the water). The rain figure is the total of
the 4 h ending at that onset, so it needs no later data.
"""
from __future__ import annotations

import hashlib
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from sqlalchemy import delete, select

from .. import tide as tide_mod
from ..db import repo, schema
from . import episodes as episodes_mod
from . import events as events_mod
from . import outcomes

DISCLAIMER = "Screening suggestion; site survey needed."
FIXED_PRIORITY = {"SUG-5": "medium", "SUG-6": "low", "SUG-7": "low"}
DEPTH_RANK = {"ankle": 1, "knee": 2, "above_knee": 3}
HOME_DEPTHS = ("knee", "above_knee")
JPS_GUIDE_MM = 60.0               # "convective rain more than 60 mm in 2-4 hours may cause flash floods"
RAIN_WINDOW_H = 4                 # the 4 h total ending at onset = max over the 2/3/4 h windows ending there
MIN_FLOODS_SUG1, MIN_FLOODS_SUG2, TIDE_SHARE, TIDE_WINDOW_H = 3, 2, 0.7, 2.0
NEIGHBOUR_M, NEIGHBOUR_MIN, ADJACENT_M = 500.0, 3, 30.0
CLUSTER_MIN, REPEAT_MIN, HIGH_SUSCEPTIBILITY = 3, 2, 4
READINESS_MIN, MISSED_MIN, STALE_MAX = 5, 2, 0.10
FLOOD_GAP = timedelta(hours=6)    # confirmed alerts on a street closer than this are one flood
NEWS_BEFORE, NEWS_AFTER = timedelta(hours=3), timedelta(hours=6)    # same window as outcomes.news_outcomes
GEO = Path(__file__).resolve().parents[2] / "assets" / "geo"
SLOT_MIN = 15

OnsetRain = Callable[[str, datetime], "float | None"]


def _sug5_top_n() -> int:
    import yaml
    with open(GEO.parents[1] / "config" / "rules.yaml", encoding="utf-8") as f:
        return int(yaml.safe_load(f)["suggestions"]["sug5_top_n"])


# ---------- station health ----------

def station_health(readings: pd.DataFrame, date_from: date, date_to: date, names: dict[str, str] | None = None, *,
                   only: set[str] | list[str] | None = None, detail: bool = False) -> list[dict]:
    """[{graph_id, name, stale_pct}] (stale_pct is a 0-1 fraction) over [date_from, date_to] inclusive, worst first.

    `readings`: graph_id, kind ('rf'|'wl'), time_local, rain_15min_mm, wl_m, AFTER QC (floodready.qc), so a reading the
    QC blanked (including a gauge in dead state) is NaN. A 15-minute slot is stale when its series has no valid value
    in it (blanked, NaN or no row). A station with rain and river series reports its worse series.

    Only COVERED slots count: a series is judged from max(period start, its first row) to min(period end, the last row
    of that kind in `readings`, i.e. where the archive ends), so future or not-yet-archived time is never "offline".
    A series with no covered slot is skipped. `only` limits the output to those stations (coverage still uses all).
    `detail=True` adds `series` ('rf'|'wl', the worse one), `covered_from` and `covered_to` (ISO)."""
    if readings is None or readings.empty:
        return []
    start = pd.Timestamp(date_from)
    last_slot = pd.Timestamp(date_to) + pd.Timedelta(days=1) - pd.Timedelta(minutes=SLOT_MIN)
    freq = f"{SLOT_MIN}min"
    kind_end = readings.groupby("kind")["time_local"].max().dt.floor(freq).to_dict()
    names = names or {}
    keep = set(only) if only is not None else None
    worst: dict[str, dict] = {}
    for (gid, kind), part in readings.groupby(["graph_id", "kind"]):
        if keep is not None and gid not in keep:
            continue
        col = "rain_15min_mm" if kind == "rf" else "wl_m"
        cov_from = max(start, part["time_local"].min().floor(freq))
        cov_to = min(last_slot, kind_end[kind])
        if cov_to < cov_from:
            continue
        slots = int((cov_to - cov_from) / pd.Timedelta(minutes=SLOT_MIN)) + 1
        times = part.loc[part[col].notna(), "time_local"].dt.floor(freq)
        valid = times[(times >= cov_from) & (times <= cov_to)].nunique()
        stale = round(1 - min(valid, slots) / slots, 3)
        if gid not in worst or stale > worst[gid]["stale_pct"]:
            worst[gid] = {"graph_id": gid, "name": names.get(gid, gid), "stale_pct": stale, "series": kind,
                          "covered_from": cov_from.isoformat(), "covered_to": cov_to.isoformat()}
    out = sorted(worst.values(), key=lambda h: (-h["stale_pct"], h["graph_id"]))
    return out if detail else [{k: h[k] for k in ("graph_id", "name", "stale_pct")} for h in out]


def onset_rain_from_archive(readings: pd.DataFrame, mapping: dict | None, window_h: int = RAIN_WINDOW_H) -> OnsetRain:
    """onset_rain(street, t): the highest `window_h`-hour rain total ending AT t (no later reading is used) among the
    street's rain gauges, from QC-cleaned archive readings; None when the street has no gauge mapping or no valid reading."""
    rf = readings[readings["kind"] == "rf"]
    series = {g: s.set_index("time_local")["rain_15min_mm"].sort_index() for g, s in rf.groupby("graph_id")}
    span = pd.Timedelta(hours=window_h)

    def onset_rain(street_id: str, t: datetime) -> float | None:
        totals = []
        for g in ((mapping or {}).get(street_id) or {}).get("rf", []):
            s = series.get(g)
            if s is None:
                continue
            w = s.loc[pd.Timestamp(t) - span + pd.Timedelta(seconds=1):pd.Timestamp(t)].dropna()
            if len(w):
                totals.append(float(w.sum()))
        return max(totals) if totals else None

    return onset_rain


# ---------- helpers ----------

def _make_id(rule: str, key: str, date_from: date, date_to: date) -> str:
    period = f"{date_from:%y%m%d}-{date_to:%y%m%d}"
    sid = f"s_{rule.lower().replace('-', '')}_{key}_{period}"
    if len(sid) > 40:
        sid = f"s_{rule.lower().replace('-', '')}_{hashlib.sha1(key.encode()).hexdigest()[:10]}_{period}"
    return sid


def _suggestion(rule: str, key: str, street_id: str, street_name: str, text: str, evidence: dict,
                date_from: date, date_to: date, priority: str) -> dict:
    return {"id": _make_id(rule, key, date_from, date_to), "street_id": street_id, "street_name": street_name,
            "rule": rule, "priority": priority, "text": f"{text} {DISCLAIMER}", "evidence": evidence,
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


def _news(events, street_ids: set[str]) -> tuple[pd.DataFrame, set[str]]:
    """(normalised events usable for matching an alert, event_ids that name homes affected).

    One shared reader (`stats.events.normalise`: checked rows only, `street_ids` split, `event_date` fallback, onset only
    at minute/hour precision). Rows without a street or an onset cannot be matched to an alert and are left out."""
    if events is None:
        return pd.DataFrame(), set()
    homes: set[str] = set()
    if "homes_affected" in events.columns and "event_id" in events.columns:
        n = pd.to_numeric(events["homes_affected"], errors="coerce")
        homes = set(events.loc[n > 0, "event_id"].astype(str))
    ev = events_mod.normalise(events, street_ids=street_ids)
    ev = ev[ev["street_id"].notna() & ev["onset"].notna()].copy()
    ev["date_precision"] = ev["date_precision"].replace("", "hour")
    ev.attrs["normalised"] = True
    return ev, homes


def _observations(conn, alerts: list[dict], news: pd.DataFrame, homes: set[str]) -> dict[str, dict]:
    """alert_id -> {obs, depth, homes} for each CONFIRMED nowcast alert.

    Confirmed = non-demo resident answers or a REAL sensor (outcomes.alert_outcome) or a checked news event
    (outcomes.news_outcomes). obs = earliest observation time (first usable yes, first real sensor exceedance, news
    onset) or None; depth = deepest depth on the usable yes answers; homes = a matching news row names homes affected."""
    rows = [a for a in alerts if a["kind"] == "alert"]
    answers: dict[str, list[dict]] = defaultdict(list)
    for r in repo.list_answers(conn):
        if r["alert_id"] and r["source"] != "demo":
            answers[r["alert_id"]].append(r)
    devices, threshold = repo.sensor_devices(), repo.sensor_threshold_cm()
    real = [{"device_id": r.device_id, "time_local": r.time_local, "level_cm": r.level_cm}
            for r in conn.execute(select(schema.sensor_readings).where(
                schema.sensor_readings.c.simulated.is_(False), schema.sensor_readings.c.level_cm > threshold))]
    news_ids = set(outcomes.news_outcomes(news, rows)) if len(news) else set()
    by_street = {sid: g for sid, g in news.groupby("street_id")} if len(news) else {}
    out: dict[str, dict] = {}
    for a in rows:
        issued = outcomes._dt(a["issued_at"])
        mine = {d for d, streets in devices.items() if a["street_id"] in streets}
        sensor = [r for r in real if r["device_id"] in mine and issued <= outcomes._dt(r["time_local"]) <= issued + outcomes.WINDOW]
        hit = outcomes.sensor_above(sensor, issued, threshold)
        verdict = outcomes.alert_outcome(answers.get(a["alert_id"], []), hit, issued_at=issued)
        if verdict != "confirmed" and a["alert_id"] not in news_ids:
            continue
        yes = [u for u in outcomes._usable(answers.get(a["alert_id"], []), issued, outcomes.WINDOW).values()
               if u["answer"] == "yes"]
        times = [outcomes._dt(u["answered_at"]) for u in yes] + [outcomes._dt(r["time_local"]) for r in sensor]
        matched = []
        if a["alert_id"] in news_ids and a["street_id"] in by_street:
            g = by_street[a["street_id"]]
            matched = [(pd.Timestamp(o).to_pydatetime(), str(e)) for o, e in zip(g["onset"], g["event_id"])
                       if issued - NEWS_BEFORE <= pd.Timestamp(o).to_pydatetime() <= issued + NEWS_AFTER]
        times += [o for o, _ in matched]
        depths = [u["depth"] for u in yes if u.get("depth") in DEPTH_RANK]
        out[a["alert_id"]] = {"obs": min(times) if times else None,
                              "depth": max(depths, key=DEPTH_RANK.get) if depths else None,
                              "homes": any(e in homes for _, e in matched)}
    return out


def _floods(alerts: list[dict], conf: dict[str, dict]) -> dict[str, list[dict]]:
    """street -> floods {start, onset, depth, homes} sorted by start. A flood is a cluster of confirmed alerts less than
    6 h apart; start = its first alert, onset = its earliest observation (None if there is none)."""
    by_street: dict[str, list[tuple[datetime, dict]]] = defaultdict(list)
    for a in alerts:
        if a["alert_id"] in conf:
            by_street[a["street_id"]].append((outcomes._dt(a["issued_at"]), conf[a["alert_id"]]))
    out: dict[str, list[dict]] = {}
    for street, items in by_street.items():
        items.sort(key=lambda x: x[0])
        floods: list[dict] = []
        last = None
        for t, info in items:
            if not floods or t - last >= FLOOD_GAP:
                floods.append({"start": t, "obs": [], "depths": [], "homes": False})
            last = t
            f = floods[-1]
            if info["obs"] is not None:
                f["obs"].append(info["obs"])
            if info["depth"]:
                f["depths"].append(info["depth"])
            f["homes"] = f["homes"] or info["homes"]
        out[street] = [{"start": f["start"], "onset": min(f["obs"]) if f["obs"] else None,
                        "depth": max(f["depths"], key=DEPTH_RANK.get) if f["depths"] else None, "homes": f["homes"]}
                       for f in floods]
    return out


def _in(ts: datetime, start: datetime, end: datetime) -> bool:
    return start <= ts < end


def _severity(floods: list[dict]) -> tuple[str, dict]:
    """(priority, evidence extras) for floods behind SUG-1..4: high when knee depth or above, or homes affected."""
    depths = [f["depth"] for f in floods if f["depth"]]
    deepest = max(depths, key=DEPTH_RANK.get) if depths else None
    homes = any(f["homes"] for f in floods)
    high = (deepest in HOME_DEPTHS) or homes
    return ("high" if high else "medium"), {"max_depth": deepest, "homes_affected": homes}


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
                streets=None, onset_rain: OnsetRain | None = None, events: pd.DataFrame | None = None,
                street_stations: dict | None = None, station_names: dict[str, str] | None = None,
                sug5_top_n: int | None = None) -> list[dict]:
    """SUG-1..SUG-7 for [date_from, date_to] inclusive, as Suggestion dicts (status 'open', note None), highest priority first.

    tide: hourly table (time_local, tide_height_m, hours_to_high_tide) or None (SUG-2 then yields nothing).
    station_health: [{graph_id, name, stale_pct}] (see `station_health`; optional `series`, `covered_from`, `covered_to`).
    streets: GeoDataFrame (street_id, name, susceptibility, centroid_lat/lon, geometry); default assets/geo/*_streets.geojson.
    onset_rain(street_id, onset) -> mm of rain in the 4 h ending at the flood onset (earliest observation), or None;
    without it SUG-1 yields nothing. `onset_rain_from_archive` builds one.
    street_stations/station_names: street -> {wl: river station} mapping and graph_id -> name (SUG-5 evidence).
    sug5_top_n: SUG-5 cap, default `suggestions.sug5_top_n` of config/rules.yaml.
    events: the raw labelled events frame (read with dtype=str); only checked rows count (see stats/events.py)."""
    if streets is None:
        streets = _load_streets()
    name_of, susc = _names(streets)
    start, end = datetime.combine(date_from, datetime.min.time()), datetime.combine(date_to + timedelta(days=1), datetime.min.time())
    prev_start, prev_end = (pd.Timestamp(start) - pd.DateOffset(years=1)).to_pydatetime(), (pd.Timestamp(end) - pd.DateOffset(years=1)).to_pydatetime()
    alerts = repo.list_alerts(conn, include_replay=False, include_backfill=True, count_simulated_sensor=False,
                              since=prev_start)
    alerts = [a for a in alerts if a.get("horizon", "nowcast") == "nowcast"]       # Outlook rows are not episodes or floods
    for a in alerts:
        a["issued_at"] = outcomes._dt(a["issued_at"]).isoformat()
    news, homes = _news(events, set(name_of))
    all_floods = _floods(alerts, _observations(conn, alerts, news, homes))
    floods = {s: [f for f in fs if _in(f["start"], start, end)] for s, fs in all_floods.items()}
    floods = {s: fs for s, fs in floods.items() if fs}
    last_year = {s: [f for f in fs if _in(f["start"], prev_start, prev_end)] for s, fs in all_floods.items()}
    out: list[dict] = []

    def name(sid: str) -> str:
        return name_of.get(sid, sid)

    def add(rule, key, sid, text, evidence, priority=None, sname=None):
        out.append(_suggestion(rule, key, sid, sname or name(sid), text, evidence, date_from, date_to,
                               priority or FIXED_PRIORITY[rule]))

    for sid, fs in sorted(floods.items()):
        starts = [f["start"] for f in fs]
        dates = [_iso(t) for t in starts]
        # SUG-1 drainage capacity: rain in the 4 h ending at the first observation of each flood
        if onset_rain is not None:
            known = [(f, onset_rain(sid, f["onset"])) for f in fs if f["onset"] is not None]
            known = [(f, r) for f, r in known if r is not None]
            if len(known) >= MIN_FLOODS_SUG1 and statistics.median(r for _, r in known) < JPS_GUIDE_MM:
                med = statistics.median(r for _, r in known)
                prio, sev = _severity([f for f, _ in known])
                nbr = _neighbours(streets, sid, susc)
                ev = {"flood_dates": [_iso(f["onset"]) for f, _ in known],
                      "rain_at_onset_mm": [round(float(r), 1) for _, r in known],
                      "median_rain_mm": round(float(med), 1), "jps_guide_mm": JPS_GUIDE_MM, **sev,
                      "notes": f"Median rain {med:.0f} mm in the {RAIN_WINDOW_H} h ending at the first observation of each flood "
                               f"(highest total among the street's gauges; QC ran on each gauge's full archive) is below the JPS guide of "
                               f"{JPS_GUIDE_MM:.0f} mm in 2-4 h."}
                if nbr:
                    ev["neighbour_streets"] = len(nbr)
                    ev["neighbour_floods"] = sum(len(floods.get(n, [])) for n in nbr)
                add("SUG-1", sid, sid, f"{name(sid)} needs a drainage capacity review / upgrade: it floods with less rain than the JPS guide.", ev, prio)
        # SUG-2 tidal backflow (flood time = first confirmed alert of the flood)
        if tide is not None and len(fs) >= MIN_FLOODS_SUG2:
            hrs = tide_mod.tide_at(tide, pd.DatetimeIndex(starts))["hours_to_high_tide"].to_numpy()
            ok = ~np.isnan(hrs)
            if ok.sum() >= MIN_FLOODS_SUG2:
                share = float((np.abs(hrs[ok]) <= TIDE_WINDOW_H).mean())
                if share >= TIDE_SHARE:
                    prio, sev = _severity([f for f, k in zip(fs, ok) if k])
                    add("SUG-2", sid, sid, f"Check outfall flap gates / backflow valves draining {name(sid)}.",
                        {"flood_dates": [d for d, k in zip(dates, ok) if k],
                         "hours_to_high_tide": [round(float(h), 1) for h in hrs[ok]], "share_near_high_tide": round(share, 2), **sev,
                         "notes": f"{share:.0%} of {int(ok.sum())} floods began within {TIDE_WINDOW_H:.0f} h of high tide."}, prio)
        # SUG-3 blockage / maintenance
        prev = len(last_year.get(sid, []))
        nbr = _neighbours(streets, sid, susc)
        quiet = [n for n in nbr if not floods.get(n)]
        prio, sev = _severity(fs)
        if len(fs) >= REPEAT_MIN and len(nbr) >= NEIGHBOUR_MIN and len(quiet) == len(nbr):
            add("SUG-3", sid + "~nbr", sid, f"Inspect and clear drains and culverts on {name(sid)} before the monsoon.",
                {"flood_dates": dates, "neighbours_without_floods": len(quiet), **sev,
                 "notes": f"{name(sid)} flooded {len(fs)} times while all {len(nbr)} neighbours within {NEIGHBOUR_M:.0f} m of similar susceptibility did not (their rain is not compared separately)."}, prio)
        if prev >= 1 and len(fs) >= REPEAT_MIN and len(fs) >= 2 * prev:
            add("SUG-3", sid + "~yoy", sid, f"Inspect and clear drains and culverts on {name(sid)} before the monsoon.",
                {"flood_dates": dates, "floods_this_period": len(fs), "floods_same_period_last_year": prev, **sev,
                 "notes": f"{len(fs)} floods this period against {prev} in the same period a year earlier."}, prio)

    # SUG-4 storage / retention
    if streets is not None and floods:
        cand = [s for s, fs in floods.items() if len(fs) >= REPEAT_MIN and susc.get(s, 0) >= HIGH_SUSCEPTIBILITY]
        for group in _clusters(streets, cand):
            days = sum(len({f["start"].date() for f in floods[s]}) for s in group)
            names = [name(s) for s in group]
            label = ", ".join(names[:3]) + (f" and {len(names) - 3} more" if len(names) > 3 else "")
            prio, sev = _severity([f for s in group for f in floods[s]])
            add("SUG-4", group[0], group[0], f"Area around {label} is a candidate for retention / on-site storage.",
                {"street_ids": group, "flood_dates": sorted({_iso(f["start"]) for s in group for f in floods[s]}),
                 "total_flood_days": days, **sev,
                 "notes": f"{len(group)} adjacent high-susceptibility streets with repeated confirmed floods. Homes nearby: not available."},
                prio, sname=names[0])

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
              "episode_dates": sorted(_iso(e["start"]) for e in eps),
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
            series = h.get("series")
            tail = {"wl": "consider a backup river-level station.",
                    "rf": "consider a backup station or our own rain gauge."}.get(series, "consider a backup station or our own gauge.")
            what = {"wl": "river level gauge", "rf": "rain gauge"}.get(series)
            subject = f"JPS station {h['name']}" + (f" ({what})" if what else "")
            ev = {"graph_id": h["graph_id"], "stale_pct": h["stale_pct"],
                  "stale_hours": round(((date_to - date_from).days + 1) * 24 * h["stale_pct"], 1),
                  "notes": "Stale = no valid reading in the 15-minute slot (missing, or blanked by QC including dead-gauge time), counted only over the covered window."}
            for k in ("series", "covered_from", "covered_to"):
                if h.get(k) is not None:
                    ev[k] = h[k]
            add("SUG-7", h["graph_id"], f"station:{h['graph_id']}",
                f"{subject} is often offline ({h['stale_pct']:.0%} of the covered period without valid data); {tail}", ev,
                sname=h["name"])

    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(out, key=lambda s: (order[s["priority"]], s["rule"], s["id"]))


def save(conn, items: list[dict], date_from: date, date_to: date, *, township: str | None = None,
         station_ids: list[str] | tuple[str, ...] = ()) -> int:
    """Upsert into the suggestions table. status/note are NOT written, so an existing row keeps its admin decision.

    With `township`, rows of the same period for that township's streets (and `station_ids`) that are still open with no
    note and were not regenerated are deleted (they no longer fire); anything an admin touched stays."""
    keep_ids = {s["id"] for s in items}
    if township is not None:
        t = schema.suggestions.c
        scope = t.street_id.like(f"{township}-%")
        if station_ids:
            scope = scope | t.street_id.in_([f"station:{g}" for g in station_ids])
        stale = select(t.id).where(t.period_from == date_from, t.period_to == date_to, t.status == "open",
                                   (t.note.is_(None)) | (t.note == ""), scope)
        gone = [r.id for r in conn.execute(stale) if r.id not in keep_ids]
        if gone:
            conn.execute(delete(schema.suggestions).where(t.id.in_(gone)))
    rows = []
    for s in items:
        row = {k: v for k, v in s.items() if k not in ("status", "note", "street_name")}
        row["period_from"], row["period_to"] = date_from, date_to
        rows.append(row)
    repo.upsert_suggestions(conn, rows)
    return len(rows)
