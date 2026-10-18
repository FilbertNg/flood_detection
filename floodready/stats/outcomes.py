"""Alert outcomes from resident answers, sensor readings and news labels (PRD "Live benchmark"; WP4).

Pure functions over plain dicts. Times are naive MYT or ISO strings.

Scoring rules (starting values from the PRD):
- confirmed: the sensor rose above its threshold, or at least 2 distinct devices said "yes" (1 is enough with a photo)
  within 3 h of the alert.
- not_confirmed: at least 3 devices said "no" and none said "yes".
- otherwise unverified, which is never counted as a false alarm.
- an answer from more than 1 km away counts half.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

WINDOW = timedelta(hours=3)
FAR_M = 1000.0
FAR_WEIGHT = 0.5
YES_NEEDED = 2
NO_NEEDED = 3
WARNING_LEVELS = ("warning", "danger")


def _dt(value) -> datetime | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("Asia/Kuala_Lumpur").tz_localize(None)
    return ts.to_pydatetime()


def _weight(answer: dict) -> float:
    d = answer.get("distance_m")
    return FAR_WEIGHT if d is not None and d > FAR_M else 1.0


def _usable(answers: list[dict], issued_at, window: timedelta) -> dict[str, dict]:
    """One answer per device (the earliest), spam removed, restricted to [issued_at, issued_at + window]."""
    start = _dt(issued_at)
    picked: dict[str, dict] = {}
    for a in sorted(answers, key=lambda x: str(x.get("answered_at"))):
        if a.get("review_status") == "spam":
            continue
        if start is not None:
            at = _dt(a.get("answered_at"))
            if at is None or at < start or at > start + window:
                continue
        picked.setdefault(a["device_id"], a)
    return picked


def alert_outcome(answers: list[dict], sensor_above: bool, *, issued_at=None, window: timedelta = WINDOW) -> str:
    """confirmed | not_confirmed | unverified. With `issued_at`, only answers in [issued_at, issued_at + 3 h] count."""
    if sensor_above:
        return "confirmed"
    yes = no = 0.0
    photo_yes = False
    for a in _usable(answers, issued_at, window).values():
        w = _weight(a)
        if a["answer"] == "yes":
            yes += w
            photo_yes = photo_yes or (bool(a.get("photo_path")) and w == 1.0)
        elif a["answer"] == "no":
            no += w
    if yes >= YES_NEEDED or photo_yes:
        return "confirmed"
    if yes == 0 and no >= NO_NEEDED:
        return "not_confirmed"
    return "unverified"


def sensor_above(readings: list[dict], issued_at, threshold_cm: float, *, window: timedelta = WINDOW) -> bool:
    """True when a reading (`time_local`, `level_cm`) above the threshold falls in [issued_at, issued_at + window]."""
    start = _dt(issued_at)
    return any(r["level_cm"] > threshold_cm and start <= _dt(r["time_local"]) <= start + window for r in readings)


def missed_floods(reports: list[dict], alerts: list[dict]) -> list[dict]:
    """Reports backed by 2 devices (1 with a photo) on a street with no Warning/Danger active at any time in the previous 3 h.

    Only `answer == "report"` rows count; spam and `source == "demo"` rows are ignored. Reports on one street within
    3 h of the first one form one event. Returns {street_id, first_reported_at, devices, answer_ids}, oldest first."""
    by_street: dict[str, list[dict]] = {}
    for r in reports:
        if r.get("answer") != "report" or r.get("review_status") == "spam" or r.get("source") == "demo":
            continue
        by_street.setdefault(r["street_id"], []).append(r)
    # a Warning/Danger is active from its issue until the street's next row that is not a Warning/Danger
    # (watch or all-clear); with no later row it is still active
    spans: dict[str, list[tuple[datetime, datetime | None]]] = {}
    for a in sorted(alerts, key=lambda x: str(x["issued_at"])):
        rows_ = spans.setdefault(a["street_id"], [])
        at = _dt(a["issued_at"])
        if a.get("kind") == "alert" and a.get("level") in WARNING_LEVELS:
            if not rows_ or rows_[-1][1] is not None:
                rows_.append((at, None))
        elif rows_ and rows_[-1][1] is None:
            rows_[-1] = (rows_[-1][0], at)
    out = []
    for street, rows in by_street.items():
        rows.sort(key=lambda x: str(x["answered_at"]))
        i = 0
        while i < len(rows):
            first = _dt(rows[i]["answered_at"])
            group = [r for r in rows[i:] if _dt(r["answered_at"]) <= first + WINDOW]
            i += len(group)
            devices = {r["device_id"] for r in group}
            backed = len(devices) >= 2 or any(r.get("photo_path") for r in group)
            if backed and not any(st <= first and (en is None or en >= first - WINDOW) for st, en in spans.get(street, [])):
                out.append({"street_id": street, "first_reported_at": first.isoformat(), "devices": len(devices),
                            "answer_ids": [r["answer_id"] for r in group]})
    return sorted(out, key=lambda m: m["first_reported_at"])


def news_outcomes(events: pd.DataFrame, alerts: list[dict]) -> dict[str, str]:
    """alert_id -> "confirmed" for each alert on a street with a labelled flood (`flooded == 1`) that started between
    3 h before and 6 h after the alert. Needs the columns `street_id`, `start_time_local`, `flooded`; events whose
    time precision is coarser than an hour (`date_precision` day/month/season) never match."""
    if events is None or events.empty or not {"street_id", "start_time_local", "flooded"} <= set(events.columns):
        return {}
    ev = events[events["flooded"].astype(str).isin(["1", "1.0", "True"])]
    if "date_precision" in ev.columns:
        ev = ev[ev["date_precision"].isin(["minute", "hour"])]
    times: dict[str, list[datetime]] = {}
    for sid, ts in zip(ev["street_id"], ev["start_time_local"]):
        t = _dt(ts)
        if t is not None and isinstance(sid, str):
            times.setdefault(sid, []).append(t)
    out = {}
    for a in alerts:
        if a.get("kind") != "alert":
            continue
        issued = _dt(a["issued_at"])
        if any(issued - timedelta(hours=3) <= t <= issued + timedelta(hours=6) for t in times.get(a["street_id"], [])):
            out[a["alert_id"]] = "confirmed"
    return out
