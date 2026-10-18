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


def _events(events: pd.DataFrame | None, floods: set[tuple[str, date]], date_from: date, date_to: date,
            street_names: dict[str, str]) -> list[dict]:
    out, covered = [], set()
    if events is not None and not events.empty and {"event_id", "start_time_local", "flooded"} <= set(events.columns):
        for _, r in events.iterrows():
            start = statistics.naive(r["start_time_local"])
            if str(r["flooded"]) not in ("1", "1.0", "True") or start is None or not date_from <= start.date() <= date_to:
                continue
            street = r.get("street_id") if isinstance(r.get("street_id"), str) else None
            if street:
                covered.add((street, start.date()))
            place = r.get("place_name")
            url = r.get("source_url")
            out.append({"event_id": str(r["event_id"]), "date": start.date().isoformat(),
                        "place": place if isinstance(place, str) else (street_names.get(street, street) if street else ""),
                        "street_ids": [street] if street else [],
                        "source_type": r.get("source_type") if isinstance(r.get("source_type"), str) else "news",
                        "source_url": url if isinstance(url, str) and url else None})
    for street, day in sorted(floods - covered, key=lambda k: (k[1], k[0])):
        out.append({"event_id": f"APP-{day.isoformat()}-{street}", "date": day.isoformat(),
                    "place": street_names.get(street, street), "street_ids": [street],
                    "source_type": "app_report", "source_url": None})
    return sorted(out, key=lambda e: (e["date"], e["event_id"]))


def monthly_report(conn, month: str, *, street_names: dict[str, str] | None = None, events: pd.DataFrame | None = None,
                   readings: pd.DataFrame | None = None, stations: pd.DataFrame | None = None,
                   street_stations: dict | None = None) -> dict:
    """The `Report` object for a calendar month ("2024-11"). Raises ValueError for a malformed month."""
    date_from, date_to = month_range(month)
    names = street_names or {}
    s, floods = statistics.analyse(conn, date_from, date_to, street_names=names, events=events, readings=readings,
                                   stations=stations, street_stations=street_stations)
    return {
        "month": month,
        "summary": s["kpis"],
        "events": _events(events, set(floods), date_from, date_to, names),
        "top_streets": [r for r in s["by_street"] if r["floods"] or r["alerts"]][:TOP_STREETS],
        "suggestions": [suggestion_view(r, names) for r in repo.list_suggestions(conn, date_from, date_to)],
        "data_health": s["station_health"],
    }
