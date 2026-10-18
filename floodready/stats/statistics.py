"""Statistics for the Admin app (`GET /admin/stats`, WP8; contract `Stats` in packages/shared/src/api/types.ts).

Only real evidence counts: backfill and live alerts (never replay), resident answers that are not `source='demo'`
and not spam, real (not simulated) sensor readings, and labelled news events. Every function is pure over the
database connection and plain inputs, so the numbers can be checked by hand.

Definitions
- alert row: an `alerts` row with kind "alert" (all-clears are not alert rows). The engine flaps (alert, all-clear,
  alert ... every 15-30 min), so rows are NOT events. Statistics count EPISODES.
- episode (see `episodes`): per street, from an alert row to the street's next all-clear, or to the end of the data if
  none comes. Later alert rows inside the open episode belong to it, and so does a new alert row that starts within
  `alerts.cooldown_min` (config/rules.yaml) of the previous all-clear (the same event flapping). Its level is the
  highest level reached, its start is its first alert row. An episode counts in the period its start falls in.
  `kpis.alerts` is the number of episodes; `kpis.alert_rows` keeps the raw row count.
- episode outcome: confirmed if any of its rows is confirmed (or a news event matches one), else not_confirmed if any
  row is, else unverified. The confirmation rate is per episode.
- outcome: confirmed / not_confirmed / unverified from `repo.list_alerts` (answers + sensor), or confirmed when a
  labelled news event matches (`outcomes.news_outcomes`). Unverified is never a false alarm.
- confirmation_rate = confirmed / (confirmed + not_confirmed); 0 when both are 0 (the type is not nullable, the UI
  shows n/a from the counts).
- flood: a distinct (street, date) with a confirmed alert or a labelled news flood. Its onset is the news
  `start_time_local` (minute/hour precision), else the earliest real "yes" answer of the confirmed alert.
- lead time: onset minus the first alert on that street in the 6 h before the onset; floods with no earlier alert
  or no onset time are skipped.
- rain at onset: the largest 2 h / 3 h / 4 h rain sum ending at the onset (15-min floor), maximum over the street's
  rain gauges. Only floods with an onset time have one.
- station health: share of the 15-min slots of the period (up to now) with no value, worst of the station's series.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from statistics import median

import pandas as pd

from ..db import repo
from ..db.repo import _alerts_cfg
from ..jobs import now_myt
from . import outcomes

LEAD_LOOKBACK = timedelta(hours=6)
PRECISE = ("minute", "hour")
SLOT = timedelta(minutes=15)


def naive(value) -> datetime | None:
    """Naive MYT datetime from a datetime, ISO string (with or without +08:00) or pandas value."""
    if value is None or (isinstance(value, float) and pd.isna(value)) or value is pd.NaT:
        return None
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("Asia/Kuala_Lumpur").tz_localize(None)
    return ts.to_pydatetime()


LEVEL_RANK = {"watch": 1, "warning": 2, "danger": 3}
OUTCOME_RANK = {"confirmed": 2, "not_confirmed": 1, "unverified": 0}


def cooldown() -> timedelta:
    return timedelta(minutes=float(_alerts_cfg().get("cooldown_min", 60)))


def episodes(rows: list[dict], merge_within: timedelta | None = None) -> list[dict]:
    """Group alert/all-clear rows (AlertSummary dicts, any streets, any order) into episodes per street.

    Rule: an alert row opens an episode when the street has none open. It stays open until an all-clear row. An alert
    row that comes after an all-clear starts a NEW episode, unless it is issued within `merge_within` (default
    `alerts.cooldown_min`) of that all-clear, in which case the episode is reopened (flapping is one event).
    Returns [{street_id, start, end (None while open), level, rows: [alert rows]}] sorted by start."""
    merge_within = cooldown() if merge_within is None else merge_within
    by_street: dict[str, list[dict]] = {}
    for r in rows:
        by_street.setdefault(r["street_id"], []).append(r)
    out = []
    for street, items in by_street.items():
        cur = None
        for r in sorted(items, key=lambda x: (naive(x["issued_at"]), x["kind"] == "alert")):
            at = naive(r["issued_at"])
            if r["kind"] == "alert":
                if cur is not None and (cur["end"] is None or at - cur["end"] <= merge_within):
                    cur["end"] = None
                else:
                    cur = {"street_id": street, "start": at, "end": None, "level": r["level"], "rows": []}
                    out.append(cur)
                cur["rows"].append(r)
                if LEVEL_RANK.get(r["level"], 0) > LEVEL_RANK.get(cur["level"], 0):
                    cur["level"] = r["level"]
            elif cur is not None and cur["end"] is None:
                cur["end"] = at
    return sorted(out, key=lambda e: (e["start"], e["street_id"]))


def news_floods(events: pd.DataFrame | None, date_from: date, date_to: date) -> dict[tuple[str, date], datetime | None]:
    """(street_id, date) -> onset (None when the time is not precise) for labelled floods (`flooded == 1`) in the period."""
    if events is None or events.empty or not {"street_id", "start_time_local", "flooded"} <= set(events.columns):
        return {}
    out: dict[tuple[str, date], datetime | None] = {}
    for _, row in events.iterrows():
        if str(row["flooded"]) not in ("1", "1.0", "True") or not isinstance(row["street_id"], str):
            continue
        start = naive(row["start_time_local"])
        if start is None or not date_from <= start.date() <= date_to:
            continue
        precise = row.get("date_precision") in PRECISE if "date_precision" in events.columns else True
        key = (row["street_id"], start.date())
        out[key] = start if precise else out.get(key)
    return out


def rain_at_onset(readings: pd.DataFrame, gauges: list[str] | None, onset: datetime) -> float | None:
    """Largest 2/3/4 h rain sum ending at `onset` (floored to 15 min), maximum over `gauges` (None = every rain gauge)."""
    rf = readings[readings["kind"] == "rf"]
    if gauges is not None:
        rf = rf[rf["graph_id"].isin(gauges)]
    end = pd.Timestamp(onset).floor("15min")
    window = rf[(rf["time_local"] > end - pd.Timedelta(hours=4)) & (rf["time_local"] <= end) & rf["rain_15min_mm"].notna()]
    best = None
    for _, g in window.groupby("graph_id"):
        for hours in (2, 3, 4):
            part = g[g["time_local"] > end - pd.Timedelta(hours=hours)]
            if not part.empty:
                total = float(part["rain_15min_mm"].sum())
                best = total if best is None else max(best, total)
    return None if best is None else round(best, 1)


def station_health(readings: pd.DataFrame, stations: pd.DataFrame, date_from: date, date_to: date,
                   now: datetime | None = None) -> list[dict]:
    """[{graph_id, name, stale_pct}] for every station of `stations` (graph_id, kind, name), worst first.
    `stale_pct` is a fraction 0..1 of the period's 15-min slots (up to `now`) with no value; a station with both rain
    and level series reports the worse one. A station with no rows at all is 1.0."""
    start = datetime.combine(date_from, datetime.min.time())
    end = min(datetime.combine(date_to, datetime.min.time()) + timedelta(days=1), (now or now_myt()).replace(tzinfo=None))
    slots = int((end - start) / SLOT)
    if slots <= 0 or stations is None or stations.empty:
        return []
    in_period = readings[(readings["time_local"] >= pd.Timestamp(start)) & (readings["time_local"] < pd.Timestamp(end))]
    out: dict[str, dict] = {}
    for (graph_id, kind), s in stations.assign(kind=stations["kind"].str.lower()).groupby(["graph_id", "kind"]):
        col = "rain_15min_mm" if kind == "rf" else "wl_m"
        rows = in_period[(in_period["graph_id"] == graph_id) & (in_period["kind"] == kind) & in_period[col].notna()]
        stale = 1 - min(rows["time_local"].nunique(), slots) / slots
        cur = out.setdefault(graph_id, {"graph_id": graph_id, "name": None, "stale_pct": 0.0})
        cur["stale_pct"] = max(cur["stale_pct"], stale)
        cur["name"] = cur["name"] or next((n for n in s["name"] if isinstance(n, str) and n), None)
    rows = [{"graph_id": r["graph_id"], "name": r["name"] or r["graph_id"], "stale_pct": round(r["stale_pct"], 4)}
            for r in out.values()]
    return sorted(rows, key=lambda r: (-r["stale_pct"], r["graph_id"]))


def stats(conn, date_from: date, date_to: date, **kw) -> dict:
    """The `Stats` object for [date_from, date_to] inclusive; keywords as in `analyse`."""
    return analyse(conn, date_from, date_to, **kw)[0]


def analyse(conn, date_from: date, date_to: date, *, street_names: dict[str, str] | None = None,
          events: pd.DataFrame | None = None, readings: pd.DataFrame | None = None,
          stations: pd.DataFrame | None = None, street_stations: dict | None = None,
          now: datetime | None = None) -> tuple[dict, dict[tuple[str, date], datetime | None]]:
    """(`Stats`, floods) for [date_from, date_to] inclusive (see the module docstring for every definition);
    floods maps (street_id, date) -> onset or None.

    `events`: labelled events (columns street_id, start_time_local, flooded, date_precision); `readings`
    (graph_id, kind, time_local, rain_15min_mm, wl_m) feed rain at onset and, with `stations` (graph_id, kind, name),
    station health; `street_stations` maps street_id -> {"rf": [gauge ids]}. Missing inputs give empty sections."""
    if date_from > date_to:
        raise ValueError("from must be on or before to")
    names = street_names or {}
    start = datetime.combine(date_from, datetime.min.time())
    end = datetime.combine(date_to, datetime.min.time()) + timedelta(days=1)

    everything = repo.list_alerts(conn, include_backfill=True, include_replay=False, count_simulated_sensor=False,
                                  exclude_demo=True, since=start - timedelta(days=2))
    everything = [a for a in everything if naive(a["issued_at"]) < end]
    mine = [a for a in everything if a["kind"] == "alert" and naive(a["issued_at"]) >= start]    # raw alert rows
    eps = [e for e in episodes(everything) if start <= e["start"] < end]
    ep_rows = [r for e in eps for r in e["rows"]]
    news_ids = outcomes.news_outcomes(events, ep_rows) if events is not None else {}
    final = {r["alert_id"]: ("confirmed" if news_ids.get(r["alert_id"]) else r["outcome"]) for r in ep_rows}

    def best(rows, key):
        return max((key(r) for r in rows), key=OUTCOME_RANK.get)

    for e in eps:
        e["outcome"] = best(e["rows"], lambda r: final[r["alert_id"]])
        e["resident"] = best(e["rows"], lambda r: r["outcome"])
        e["news_only"] = e["resident"] == "unverified" and any(r["alert_id"] in news_ids for r in e["rows"])
    resident_checked = sum(1 for e in eps if e["resident"] != "unverified")
    from_news = sum(1 for e in eps if e["news_only"])

    answers = [a for a in repo.list_answers(conn) if a["source"] != "demo" and a["review_status"] != "spam"]
    first_yes: dict[str, datetime] = {}
    for a in answers:
        if a["answer"] == "yes" and a["alert_id"]:
            at = naive(a["answered_at"])
            if a["alert_id"] not in first_yes or at < first_yes[a["alert_id"]]:
                first_yes[a["alert_id"]] = at

    floods: dict[tuple[str, date], datetime | None] = {}
    for a in ep_rows:
        if final[a["alert_id"]] == "confirmed":
            key = (a["street_id"], naive(a["issued_at"]).date())
            floods.setdefault(key, None)
            onset = first_yes.get(a["alert_id"])
            if onset is not None and (floods[key] is None or onset < floods[key]):
                floods[key] = onset
    for key, onset in news_floods(events, date_from, date_to).items():
        floods[key] = onset if onset is not None else floods.get(key)

    leads = []
    for (street, _), onset in floods.items():
        if onset is None:
            continue
        before = [naive(a["issued_at"]) for a in everything
                  if a["street_id"] == street and a["kind"] == "alert" and onset - LEAD_LOOKBACK <= naive(a["issued_at"]) <= onset]
        if before:
            leads.append((onset - min(before)).total_seconds() / 60)

    reports = [a for a in answers if a["answer"] == "report"]
    missed = [m for m in outcomes.missed_floods(reports, everything)
              if start <= naive(m["first_reported_at"]) < end]

    counts = {k: sum(1 for e in eps if e["outcome"] == k) for k in ("confirmed", "not_confirmed", "unverified")}
    decided = counts["confirmed"] + counts["not_confirmed"]

    weeks: dict[str, dict] = {}
    by_street: dict[str, dict] = {}
    for e in eps:
        iso = e["start"].isocalendar()
        w = weeks.setdefault(f"{iso.year}-W{iso.week:02d}", {"alerts": 0, "confirmed": 0})
        st = by_street.setdefault(e["street_id"], {"alerts": 0, "confirmed": 0, "floods": 0})
        w["alerts"] += 1
        st["alerts"] += 1
        if e["outcome"] == "confirmed":
            w["confirmed"] += 1
            st["confirmed"] += 1
    for street, _ in floods:
        by_street.setdefault(street, {"alerts": 0, "confirmed": 0, "floods": 0})["floods"] += 1

    onsets = []
    if readings is not None:
        for (street, day), onset in sorted(floods.items(), key=lambda kv: (kv[0][1], kv[0][0])):
            if onset is None:
                continue
            gauges = (street_stations or {}).get(street, {}).get("rf") or None
            mm = rain_at_onset(readings, gauges, onset)
            if mm is not None:
                onsets.append({"street_id": street, "event_date": day.isoformat(), "rain_2to4h_mm": mm})

    result = {
        "period": {"from": date_from.isoformat(), "to": date_to.isoformat()},
        "kpis": {"alerts": len(eps), **counts,
                 "alert_rows": len(mine),
                 "by_level": {lv: sum(1 for e in eps if e["level"] == lv) for lv in LEVEL_RANK},
                 "street_days_with_alert": len({(r["street_id"], naive(r["issued_at"]).date()) for r in mine}),
                 "confirmation_rate": counts["confirmed"] / decided if decided else 0,
                 "missed_floods": len(missed),
                 "median_lead_min": float(median(leads)) if leads else None},
        "by_week": [{"week": k, **v} for k, v in sorted(weeks.items())],
        "by_street": [{"street_id": k, "name": names.get(k, k), **v} for k, v in
                      sorted(by_street.items(), key=lambda kv: (-kv[1]["floods"], -kv[1]["alerts"], kv[0]))],
        "rain_at_onset": onsets,
        "station_health": station_health(readings, stations, date_from, date_to, now)
        if readings is not None and stations is not None else [],
        "sources": {"outcomes_from_news": from_news, "outcomes_from_residents": resident_checked},
    }
    return result, floods
