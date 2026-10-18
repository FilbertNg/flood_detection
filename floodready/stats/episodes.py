"""Alert episodes: the unit that statistics and suggestions count (not raw alert rows, which flap).

An episode runs from an alert row to its all-clear (or to `period_end`, or the street's last row if still open).
A new alert starting within `cooldown` of the previous all-clear merges into the same episode. The episode's
level is the highest level reached. Shared by SUG-5 (WP7) and the statistics (WP8).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from . import outcomes

LEVEL_RANK = {"normal": 0, "watch": 1, "warning": 2, "danger": 3}


def cooldown_default() -> timedelta:
    from ..db import repo
    return timedelta(minutes=int(repo._alerts_cfg()["cooldown_min"]))


def episodes(alerts: list[dict], cooldown: timedelta | None = None, period_end: datetime | None = None) -> list[dict]:
    """alerts: AlertSummary dicts (street_id, kind 'alert'|'all_clear', level, issued_at, alert_id), any order.

    Returns [{street_id, start, end, level, alert_ids, rows}] sorted by start; `end` is the all-clear time (or
    period_end / last row when still open), `rows` the number of alert rows merged into it."""
    cooldown = cooldown_default() if cooldown is None else cooldown
    by_street: dict[str, list[dict]] = {}
    for a in alerts:
        by_street.setdefault(a["street_id"], []).append(a)
    out: list[dict] = []
    for street, rows in by_street.items():
        rows = sorted(rows, key=lambda r: (outcomes._dt(r["issued_at"]), r["kind"] == "alert"))
        cur: dict | None = None
        closed_at: datetime | None = None
        for r in rows:
            t = outcomes._dt(r["issued_at"])
            if r["kind"] == "alert":
                if cur is None:
                    cur = {"street_id": street, "start": t, "end": None, "level": r["level"], "alert_ids": [], "rows": 0}
                    out.append(cur)
                elif cur["end"] is not None:
                    if t - closed_at <= cooldown:     # flap: same episode, reopened
                        cur["end"] = None
                    else:
                        cur = {"street_id": street, "start": t, "end": None, "level": r["level"], "alert_ids": [], "rows": 0}
                        out.append(cur)
                cur["alert_ids"].append(r["alert_id"])
                cur["rows"] += 1
                if LEVEL_RANK.get(r["level"], 0) > LEVEL_RANK.get(cur["level"], 0):
                    cur["level"] = r["level"]
            elif cur is not None and cur["end"] is None:
                cur["end"] = closed_at = t
        for e in (e for e in out if e["street_id"] == street and e["end"] is None):
            e["end"] = period_end if period_end is not None else outcomes._dt(rows[-1]["issued_at"])
    return sorted(out, key=lambda e: (e["start"], e["street_id"]))
