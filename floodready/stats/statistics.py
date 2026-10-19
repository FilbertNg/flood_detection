"""Statistics for the Admin app (`GET /admin/stats`, WP8; contract `Stats` in packages/shared/src/api/types.ts).

Only real evidence counts: NOWCAST alerts of backfill and live (never replay, never Outlook), resident answers that are
not `source='demo'` and not spam, real (not simulated) sensor readings, and CHECKED labelled news events
(`stats.events.normalise`, the one reader of events.csv). Pure functions over the database connection and plain inputs.

Definitions
- alert row: an `alerts` row with kind "alert" and horizon "nowcast". The engine flaps (alert, all-clear, alert ...
  every 15-30 min), so rows are NOT events. Statistics count EPISODES. Outlook rows (one township forecast stored as
  one Watch row per street) are a different horizon and never enter these numbers.
- episode (see `stats.episodes`, shared with the suggestions): per street, from an alert row to the street's next all-clear. Later alert rows inside the
  open episode belong to it, and so does a new alert row that starts within `alerts.cooldown_min` (config/rules.yaml)
  of the previous all-clear. An open episode (no all-clear) is split when 48 h pass with no row (missed all-clears:
  API down, backfill/live boundary). Level = highest reached, start = first alert row. Episodes are built from rows
  well outside the period (14 days back, 7 days ahead) and selected by their start date, so one that crosses a period
  edge keeps all its rows (level and outcome) and is counted once, in the period it started.
  `kpis.alerts` is the number of episodes. Raw row counts stay internal (`extras`).
- episode outcome: confirmed if any of its rows is confirmed (or a checked news event matches one), else
  not_confirmed if any row is, else unverified. The confirmation rate is per episode:
  confirmed / (confirmed + not_confirmed), 0 when both are 0 (the type is not nullable, the UI shows n/a from counts).
  News can only confirm, so on the backfill the rate is structurally high: do not quote it as accuracy.
- flood: evidence of a flood on a street: a confirmed alert row, or a checked news event. Evidence on one street
  less than 12 h apart is ONE flood (so a flood over midnight counts once). Its date is the first evidence's date.
  Onset: the news `start_time_local` (minute/hour precision), else the earliest real "yes" answer.
- lead time ("lead to first report"): onset minus the first nowcast alert on that street in the 6 h before the onset;
  floods with no earlier alert or no onset time are skipped.
- rain at onset: the largest 2 h / 3 h / 4 h rain sum ending at the onset (15-min floor), maximum over the street's
  rain gauges. Only floods with an onset time have one.
- station health: share of the 15-min slots of the period (up to now) with no value, worst of the station's series.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from statistics import median

import pandas as pd

from ..db import repo
from ..jobs import now_myt
from . import episodes as episodes_mod
from . import events as events_mod
from . import outcomes

LEAD_LOOKBACK = timedelta(hours=6)
PRECISE = ("minute", "hour")
SLOT = timedelta(minutes=15)
FLOOD_MERGE = timedelta(hours=12)    # evidence this close on one street is one flood
LOOKBACK = timedelta(days=14)        # rows fetched before the period (open episodes) and after it (their continuation)
LOOKAHEAD = timedelta(days=7)


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


def flood_clusters(evidence: list[dict]) -> list[dict]:
    """Merge flood evidence per street: items {street_id, start, end, onset (or None)}, merged when the next starts
    within FLOOD_MERGE of the running end. Returns [{street_id, date, onset, news_ids}] (date of the first evidence)."""
    out: list[dict] = []
    for street in sorted({e["street_id"] for e in evidence}):
        cur = None
        for e in sorted((x for x in evidence if x["street_id"] == street), key=lambda x: x["start"]):
            if cur is not None and e["start"] <= cur["end"] + FLOOD_MERGE:
                cur["end"] = max(cur["end"], e["end"])
            else:
                cur = {"street_id": street, "date": e["start"].date(), "start": e["start"], "end": e["end"],
                       "onset": None, "precise": None, "news_ids": set()}
                out.append(cur)
            cur["news_ids"] |= e.get("news_ids", set())
            if e["onset"] is not None:
                if e.get("precise"):
                    cur["precise"] = e["onset"] if cur["precise"] is None else min(cur["precise"], e["onset"])
                else:
                    cur["onset"] = e["onset"] if cur["onset"] is None else min(cur["onset"], e["onset"])
    for c in out:
        c["onset"] = c["precise"] or c["onset"]
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
            township_name: str | None = None, now: datetime | None = None) -> tuple[dict, list[dict], dict]:
    """(`Stats`, floods, extras) for [date_from, date_to] inclusive (see the module docstring for every definition).

    `events`: the raw events.csv frame (or `events.normalise` output); `street_names` also limits everything to the
    township's streets; `readings` (graph_id, kind, time_local, rain_15min_mm, wl_m) feed rain at onset and, with
    `stations` (graph_id, kind, name), station health; `street_stations` maps street_id -> {"rf": [gauge ids]}.
    Missing inputs give empty sections. floods: [{street_id, date, onset, news_ids}]. extras: raw alert row count,
    episodes by level and street-days with an alert (not part of the API contract)."""
    if date_from > date_to:
        raise ValueError("from must be on or before to")
    names = street_names or {}
    start = datetime.combine(date_from, datetime.min.time())
    end = datetime.combine(date_to, datetime.min.time()) + timedelta(days=1)

    fetched = repo.list_alerts(conn, include_backfill=True, include_replay=False, count_simulated_sensor=False,
                               exclude_demo=True, since=start - LOOKBACK, until=end + LOOKAHEAD)
    rows = [a for a in fetched if a["horizon"] == "nowcast" and (not names or a["street_id"] in names)]
    ev = events_mod.normalise(events, street_ids=set(names) if names else None, township_name=township_name)
    alert_rows = [a for a in rows if a["kind"] == "alert"]
    news_ids = outcomes.news_outcomes(ev, alert_rows)
    final = {a["alert_id"]: ("confirmed" if news_ids.get(a["alert_id"]) else a["outcome"]) for a in alert_rows}
    mine = [a for a in alert_rows if start <= naive(a["issued_at"]) < end]

    def best(rs, key):
        return max((key(r) for r in rs), key=OUTCOME_RANK.get)

    by_id = {a["alert_id"]: a for a in alert_rows}
    eps = [e for e in episodes_mod.episodes(rows) if start <= e["start"] < end]
    for e in eps:
        members = [by_id[i] for i in e["alert_ids"]]
        e["outcome"] = best(members, lambda r: final[r["alert_id"]])
        e["resident"] = best(members, lambda r: r["outcome"])
        e["news_only"] = e["resident"] == "unverified" and any(r["alert_id"] in news_ids for r in members)
    resident_checked = sum(1 for e in eps if e["resident"] != "unverified")
    from_news = sum(1 for e in eps if e["news_only"])

    answers = [a for a in repo.list_answers(conn) if a["source"] != "demo" and a["review_status"] != "spam"]
    first_yes: dict[str, datetime] = {}
    for a in answers:
        if a["answer"] == "yes" and a["alert_id"]:
            at = naive(a["answered_at"])
            if a["alert_id"] not in first_yes or at < first_yes[a["alert_id"]]:
                first_yes[a["alert_id"]] = at

    evidence = []
    pad = timedelta(days=2)       # evidence just outside the period, so a flood over the edge is one flood
    for a in alert_rows:                                # confirmed rows count on their own date, whichever episode owns them
        if final[a["alert_id"]] == "confirmed" and start - pad <= naive(a["issued_at"]) < end + pad:
            at = naive(a["issued_at"])
            evidence.append({"street_id": a["street_id"], "start": at, "end": at, "onset": first_yes.get(a["alert_id"])})
    for _, r in ev.iterrows():
        if not isinstance(r["street_id"], str) or not date_from - pad <= r["date"] <= date_to + pad:
            continue
        if pd.notna(r["onset"]):
            t = naive(r["onset"])
            evidence.append({"street_id": r["street_id"], "start": t, "end": t, "onset": t, "precise": True,
                             "news_ids": {r["event_id"]}})
        else:
            day = datetime.combine(r["date"], datetime.min.time())
            evidence.append({"street_id": r["street_id"], "start": day, "end": day + timedelta(hours=23, minutes=59),
                             "onset": None, "news_ids": {r["event_id"]}})
    # a flood belongs to the period its first evidence falls in (like episodes), so it is never counted twice
    floods = [f for f in flood_clusters(evidence) if date_from <= f["date"] <= date_to]

    leads = []
    for f in floods:
        if f["onset"] is None:
            continue
        before = [naive(a["issued_at"]) for a in alert_rows
                  if a["street_id"] == f["street_id"] and f["onset"] - LEAD_LOOKBACK <= naive(a["issued_at"]) <= f["onset"]]
        if before:
            leads.append((f["onset"] - min(before)).total_seconds() / 60)

    reports = [a for a in answers if a["answer"] == "report"]
    missed = [m for m in outcomes.missed_floods(reports, rows) if start <= naive(m["first_reported_at"]) < end]

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
    for f in floods:
        by_street.setdefault(f["street_id"], {"alerts": 0, "confirmed": 0, "floods": 0})["floods"] += 1

    onsets = []
    if readings is not None:
        for f in sorted(floods, key=lambda f: (f["date"], f["street_id"])):
            if f["onset"] is None:
                continue
            gauges = (street_stations or {}).get(f["street_id"], {}).get("rf") or None
            mm = rain_at_onset(readings, gauges, f["onset"])
            if mm is not None:
                onsets.append({"street_id": f["street_id"], "event_date": f["date"].isoformat(), "rain_2to4h_mm": mm})

    result = {
        "period": {"from": date_from.isoformat(), "to": date_to.isoformat()},
        "kpis": {"alerts": len(eps), **counts,
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
    extras = {"alert_rows": len(mine),
              "by_level": {lv: sum(1 for e in eps if e["level"] == lv) for lv in LEVEL_RANK},
              "street_days_with_alert": len({(r["street_id"], naive(r["issued_at"]).date()) for r in mine})}
    return result, floods, extras
