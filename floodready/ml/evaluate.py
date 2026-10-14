"""Event-level evaluation of a warning signal (build plan task ML2; definitions as in docs/ml-feasibility.md).

- A crossing is the first quarter hour at or above the warning level after being below it.
- A crossing is detected if the signal fired between 3 h and 15 min before it; lead = from the first fire.
- An alarm episode starts where the signal switches on; it is false if no crossing follows within 3 h.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def event_metrics(level: pd.Series, fired: pd.Series, warning: float, lead_min: int = 15,
                  lead_max_h: float = 3.0, false_h: float = 3.0) -> dict:
    level = level.sort_index()
    fired = fired.reindex(level.index, fill_value=False).astype(bool)
    above = (level >= warning).fillna(False).astype(bool)
    crossings = level.index[(above & ~above.shift(1, fill_value=True)).to_numpy()]

    leads = []
    for t in crossings:
        window = fired[t - pd.Timedelta(hours=lead_max_h): t - pd.Timedelta(minutes=lead_min)]
        if window.any():
            leads.append((t - window[window].index[0]).total_seconds() / 60)

    starts = fired.index[(fired & ~fired.shift(1, fill_value=False)).to_numpy()]
    false = sum(1 for s in starts if not ((crossings > s) & (crossings <= s + pd.Timedelta(hours=false_h))).any())
    months = max((level.index[-1] - level.index[0]).total_seconds() / 86400 / 30.4, 1e-9) if len(level) else 0.0
    return {"crossings": len(crossings), "detected": len(leads), "leads": leads,
            "median_lead_min": float(np.median(leads)) if leads else None,
            "false_alarms": false, "months": months, "false_per_month": false / months if months else None}


def pooled(per_station: list[dict]) -> dict:
    """Sum over stations; false alarms per station-month."""
    leads = [x for m in per_station for x in m["leads"]]
    months = sum(m["months"] for m in per_station)
    false = sum(m["false_alarms"] for m in per_station)
    return {"crossings": sum(m["crossings"] for m in per_station), "detected": sum(m["detected"] for m in per_station),
            "median_lead_min": float(np.median(leads)) if leads else None, "false_alarms": false,
            "station_months": months, "false_per_station_month": false / months if months else None}


def gate(rule: dict, ml: dict, cfg: dict) -> tuple[bool, str]:
    """The evaluation gate (docs/ml-feasibility.md): may ML drive alert levels?

    (a) detects at least as many crossings as the rule with no more false alarms, or
    (b) detects at least as many with >= min_extra_lead_min more median lead and
        <= max_false_alarm_ratio x the rule's false alarms.
    """
    fa_ml, fa_rule = ml["false_per_station_month"], rule["false_per_station_month"]
    if ml["detected"] < rule["detected"]:
        return False, ""
    if fa_ml <= fa_rule:
        return True, "a"
    lead_ml, lead_rule = ml["median_lead_min"] or 0.0, rule["median_lead_min"] or 0.0
    if lead_ml >= lead_rule + cfg["min_extra_lead_min"] and fa_ml <= cfg["max_false_alarm_ratio"] * fa_rule:
        return True, "b"
    return False, ""


def pick_threshold(candidates: list[tuple[float, dict]], rule: dict, cfg: dict) -> tuple[float, bool, str]:
    """Best probability threshold: one passing (a), else (b), with the most detections.
    If none passes, the threshold with the most detections at no more false alarms
    than the rule (for display), reported as failing."""
    for criterion in ("a", "b"):
        passing = [(thr, m) for thr, m in candidates if gate(rule, m, cfg) == (True, criterion)]
        if passing:
            thr, _ = max(passing, key=lambda c: (c[1]["detected"], -c[1]["false_per_station_month"]))
            return thr, True, criterion
    safe = [(thr, m) for thr, m in candidates if m["false_per_station_month"] <= rule["false_per_station_month"]]
    if safe:
        thr, _ = max(safe, key=lambda c: (c[1]["detected"], -c[1]["false_per_station_month"]))
        return thr, False, ""
    return max(thr for thr, _ in candidates), False, ""
