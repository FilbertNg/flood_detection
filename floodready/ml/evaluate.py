"""Event-level evaluation of a warning signal (build plan task ML2; definitions as in docs/ml-feasibility.md).

- A crossing is the first quarter hour at or above the warning level after being below it.
- A crossing is detected if the signal fired between 3 h and 15 min before it; lead = from the first fire.
- An alarm episode starts where the signal switches on; it is false if no crossing follows within 3 h.
  Alarm precision = share of alarm episodes that are not false.
- Gate v2 (docs/plans/2026-10-16-IMP-ml-data-street-improvements.md section 3, pre-registered) is at the bottom.
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
    horizon = pd.Timedelta(hours=false_h)
    nxt = crossings.searchsorted(starts, side="right")  # first crossing strictly after each alarm start
    false = sum(1 for s, i in zip(starts, nxt) if i >= len(crossings) or crossings[i] > s + horizon)
    months = max((level.index[-1] - level.index[0]).total_seconds() / 86400 / 30.4, 1e-9) if len(level) else 0.0
    return {"crossings": len(crossings), "detected": len(leads), "leads": leads,
            "median_lead_min": float(np.median(leads)) if leads else None,
            "false_alarms": false, "alarms": len(starts),
            "alarm_precision": (len(starts) - false) / len(starts) if len(starts) else None,
            "months": months, "false_per_month": false / months if months else None}


def pooled(per_station: list[dict]) -> dict:
    """Sum over stations; false alarms per station-month."""
    leads = [x for m in per_station for x in m["leads"]]
    months = sum(m["months"] for m in per_station)
    false = sum(m["false_alarms"] for m in per_station)
    alarms = sum(m.get("alarms", 0) for m in per_station)
    return {"alarms": alarms, "alarm_precision": (alarms - false) / alarms if alarms else None, "crossings": sum(m["crossings"] for m in per_station), "detected": sum(m["detected"] for m in per_station),
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


# ---------------------------------------------------------------- tidal vs inland

def tidal_stations(levels: dict[str, pd.Series], lag: int = 25, threshold: float = -0.2) -> set[str]:
    """Stations whose level follows the tide: autocorrelation at `lag` quarter hours (6.25 h, half a tidal
    cycle) below `threshold`. A rain-driven river stays positively autocorrelated at that lag."""
    out = set()
    for gid, s in levels.items():
        s = s[~s.index.duplicated()].sort_index()
        if s.notna().sum() <= lag + 2:
            continue
        r = s.asfreq("15min").autocorr(lag)
        if pd.notna(r) and r < threshold:
            out.add(gid)
    return out


# ---------------------------------------------------------------- gate v2

def _fa(m: dict) -> float:
    v = m.get("false_per_station_month")
    return v if v is not None else float("inf")


def criteria(floor: dict, two_tier: dict, cfg: dict) -> dict:
    """Criteria 1 and 2 of gate v2 on one set of stations."""
    lead_floor, lead_two = floor["median_lead_min"] or 0.0, two_tier["median_lead_min"]
    lead_ok = lead_two is not None and lead_two >= lead_floor + cfg["min_extra_lead_min"]
    fa_ok = _fa(two_tier) <= cfg["max_false_alarm_ratio"] * _fa(floor)
    return {"lead_ok": bool(lead_ok), "false_alarms_ok": bool(fa_ok), "passed": bool(lead_ok and fa_ok),
            "lead_floor_min": lead_floor, "lead_two_tier_min": lead_two,
            "false_floor": _fa(floor), "false_two_tier": _fa(two_tier)}


def gate_v2(floor: dict, two_tier: dict, fresh_floor: dict | None, fresh_two_tier: dict | None, cfg: dict) -> dict:
    """Gate v2 on inland stations. Criterion 3: on fresh stations criteria 1-2 also hold when they have at
    least `min_fresh_crossings` inland crossings; otherwise they are reported but not gating."""
    main = criteria(floor, two_tier, cfg)
    fresh = criteria(fresh_floor, fresh_two_tier, cfg) if fresh_floor is not None and fresh_two_tier is not None else None
    gating = fresh is not None and fresh_floor["crossings"] >= cfg["min_fresh_crossings"]
    passed = main["passed"] and (fresh["passed"] if gating else True)
    return {"passed": passed, "main": main, "fresh": fresh, "fresh_gating": bool(gating)}


def select_theta(blocks: list[dict], thetas: list[float], max_ratio: float, prefix: str = "two_tier") -> float:
    """The theta with the most detections whose false alarms stay within `max_ratio` x the floor's, pooled over
    `blocks` (ties: fewer false alarms, then the higher theta). If none fit, the most conservative theta."""
    floor = pooled([b["metrics"]["floor"] for b in blocks])
    limit = max_ratio * _fa(floor)
    best = None
    for th in thetas:
        m = pooled([b["metrics"][f"{prefix}_{th}"] for b in blocks])
        if _fa(m) <= limit:
            key = (m["detected"], -_fa(m), th)
            if best is None or key > best[0]:
                best = (key, th)
    return best[1] if best else max(thetas)


def nested_thetas(blocks: list[dict], thetas: list[float], max_ratio: float, prefix: str = "two_tier") -> dict[int, float]:
    """Per outer fold: theta chosen on the inland blocks of the OTHER folds only."""
    folds = sorted({b["fold"] for b in blocks})
    return {k: select_theta([b for b in blocks if b["fold"] != k and b.get("inland", True)], thetas, max_ratio, prefix)
            for k in folds}


def nested_pool(blocks: list[dict], theta_by_fold: dict[int, float], prefix: str) -> dict:
    """Pooled metrics where every block uses the theta that was chosen without it."""
    return pooled([b["metrics"][f"{prefix}_{theta_by_fold[b['fold']]}"] for b in blocks])


# ---------------------------------------------------------------- calibration quality

RELIABILITY_BINS = [0.0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 1.0000001]


def reliability_table(p, y) -> pd.DataFrame:
    """Predicted-probability bins (as in docs/ml-data-eda.md section 6): rows, mean predicted, observed rate."""
    p, y = np.asarray(p, float), np.asarray(y, float)
    idx = np.digitize(p, RELIABILITY_BINS[1:-1])
    rows = []
    for i in range(len(RELIABILITY_BINS) - 1):
        sel = idx == i
        hi = min(RELIABILITY_BINS[i + 1], 1.0)
        rows.append({"bin": f"{RELIABILITY_BINS[i]:.2f}-{hi:.2f}", "n": int(sel.sum()),
                     "mean_pred": float(p[sel].mean()) if sel.any() else np.nan,
                     "observed": float(y[sel].mean()) if sel.any() else np.nan})
    return pd.DataFrame(rows)


def brier(p, y) -> float:
    return float(np.mean((np.asarray(p, float) - np.asarray(y, float)) ** 2))


def ece(p, y) -> float:
    """Expected calibration error over the reliability bins: sum of (bin share) x |mean predicted - observed|."""
    t = reliability_table(p, y)
    t = t[t.n > 0]
    return float((t.n / t.n.sum() * (t.mean_pred - t.observed).abs()).sum())
