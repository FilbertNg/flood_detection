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


MAX_OPEN_GAP = timedelta(hours=48)    # an open episode with no row for this long is cut at its last row


def episodes(alerts: list[dict], cooldown: timedelta | None = None, max_open_gap: timedelta = MAX_OPEN_GAP) -> list[dict]:
    """alerts: AlertSummary dicts (street_id, kind 'alert'|'all_clear', level, issued_at, alert_id), any order.

    Returns [{street_id, start, end, level, alert_ids, rows}] sorted by start. `end` is the all-clear time, or None
    while the episode is open; `level` is the highest level reached; `alert_ids` are the alert rows merged into it
    (to aggregate outcomes); an open episode splits when `max_open_gap` (48 h) passes with no row (the first part
    ends at its last row); `rows` = len(alert_ids). Count an episode in the period its `start` falls in."""
    cooldown = cooldown_default() if cooldown is None else cooldown
    by_street: dict[str, list[dict]] = {}
    for a in alerts:
        by_street.setdefault(a["street_id"], []).append(a)
    out: list[dict] = []
    for street, rows in by_street.items():
        rows = sorted(rows, key=lambda r: (outcomes._dt(r["issued_at"]), r["kind"] == "alert"))
        cur: dict | None = None
        closed_at: datetime | None = None
        last_t: datetime | None = None
        for r in rows:
            t = outcomes._dt(r["issued_at"])
            if cur is not None and cur["end"] is None and t - last_t > max_open_gap:
                cur["end"] = last_t
                cur = None
            last_t = t
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
    return sorted(out, key=lambda e: (e["start"], e["street_id"]))
