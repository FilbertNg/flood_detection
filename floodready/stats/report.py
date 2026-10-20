"""Monthly report for the Admin app (`GET /admin/report?month=YYYY-MM`, WP8; contract `Report`).

Every number comes from `statistics.stats` for the calendar month. Events are the labelled news floods of the month
plus resident-confirmed floods that no labelled event already covers (same street and date).
"""
from __future__ import annotations

import calendar
import re
from datetime import date

import pandas as pd

from ..db import repo
from . import events as events_mod
from . import statistics

SUFFIX = "Screening suggestion; site survey needed."
TOP_STREETS = 5


def month_range(month: str) -> tuple[date, date]:
    m = re.fullmatch(r"(\d{4})-(0[1-9]|1[0-2])", month or "")
    if not m:
        raise ValueError("month must be YYYY-MM")
    year, mon = int(m[1]), int(m[2])
    return date(year, mon, 1), date(year, mon, calendar.monthrange(year, mon)[1])


def with_suffix(text: str) -> str:
    return text if text.rstrip().endswith(SUFFIX) else f"{text.rstrip()} {SUFFIX}"


def suggestion_view(row: dict, street_names: dict[str, str] | None = None) -> dict:
    """A `Suggestion` from a `repo.list_suggestions` row (street name filled in, text ends with the fixed sentence)."""
    sid = row["street_id"]
    return {"id": row["id"], "street_id": sid or "", "street_name": (street_names or {}).get(sid, sid or ""),
            "rule": row["rule"], "priority": row["priority"], "text": with_suffix(row["text"]),
            "evidence": row["evidence"], "status": row["status"], "note": row["note"]}


def _events(ev: pd.DataFrame, floods: list[dict], date_from: date, date_to: date, street_names: dict[str, str]) -> list[dict]:
    """Checked news events of the month (one per event_id) plus floods confirmed by residents that no news event
    covers (source_type app_report). A flood over midnight is one flood, so it never appears twice."""
    out = []
    for event_id, g in ev[(ev["date"] >= date_from) & (ev["date"] <= date_to)].groupby("event_id", sort=False):
        first = g.iloc[0]
        out.append({"event_id": event_id, "date": first["date"].isoformat(), "place": first["place_name"],
                    "street_ids": [s for s in g["street_id"] if isinstance(s, str)],
                    "source_type": first["source_type"], "source_url": first["source_url"]})
    for f in floods:
        if not f["news_ids"]:
            out.append({"event_id": f"APP-{f['date'].isoformat()}-{f['street_id']}", "date": f["date"].isoformat(),
                        "place": street_names.get(f["street_id"], f["street_id"]), "street_ids": [f["street_id"]],
                        "source_type": "app_report", "source_url": None})
    return sorted(out, key=lambda e: (e["date"], e["event_id"]))


def monthly_report(conn, month: str, *, street_names: dict[str, str] | None = None, events: pd.DataFrame | None = None,
                   readings: pd.DataFrame | None = None, stations: pd.DataFrame | None = None,
                   street_stations: dict | None = None, township_name: str | None = None) -> dict:
    """The `Report` object for a calendar month ("2024-11"). Raises ValueError for a malformed month."""
    date_from, date_to = month_range(month)
    names = street_names or {}
    s, floods, _extras = statistics.analyse(conn, date_from, date_to, street_names=names, events=events, readings=readings,
                                            stations=stations, street_stations=street_stations,
                                            township_name=township_name)
    ev = events_mod.normalise(events, street_ids=set(names) if names else None, township_name=township_name)
    return {
        "month": month,
        "summary": s["kpis"],
        "events": _events(ev, floods, date_from, date_to, names),
        "top_streets": [r for r in s["by_street"] if r["floods"] or r["alerts"]][:TOP_STREETS],
        "suggestions": [suggestion_view(r, names) for r in repo.list_suggestions(conn, date_from, date_to)],
        "data_health": s["station_health"],
    }
