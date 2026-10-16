"""Quality control for JPS 15-min readings (improvements #2, rain and river-level QC).

JPS rain is a cumulative counter that the loaders difference to 15-min values, so a data gap,
a stuck counter or the 1 Jan reset produce impossible values (-3,275 to +2,050 mm per 15 min).
`clean_readings` turns the bad values into NaN (never 0) and returns what it removed, so every
consumer (rules, ML features, API) sees the same clean data and every removal is auditable.

Rules, applied in this order (a reading is flagged by the first rule that matches).
Evidence for every threshold is in docs/data-qc-report.md (regenerate with scripts/qc_report.py).

rain_negative     rain < 0. A counter cannot go down; these are resets (1 Jan, gauge restarts).
rain_implausible  rain > RAIN_MAX_15MIN_MM (100 mm per 15 min = 400 mm/h). The largest genuine
                  value in the archive is about 95 mm; the next values above 100 are counter jumps
                  (121 to 2,570 mm).
rain_after_gap    rain >= RAIN_GAP_MIN_MM in the first reading after >= GAP_MIN_MISSING_MIN of
                  missing readings, and the next reading is below RAIN_CONTINUES_MM: a counter
                  catch-up lumps the rain of the whole gap into one step and is followed by silence,
                  while a storm that began during the gap keeps raining (kept: 27233 on 2025-03-06
                  00:00 = 30.5, 24.0, 11.5 mm with 55 mm at neighbouring gauges).
rain_stuck        the same value >= RAIN_STUCK_MIN_MM at least 3 times within 24 h at one gauge.
wl_spike          river level jumps > WL_SPIKE_M in one step and returns within WL_REVERT_M of the
                  previous value on the next reading. Negative levels are valid (tidal stations'
                  datum is below sea level) and are never flagged.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

COLUMNS = ["graph_id", "kind", "time_local", "rain_15min_mm", "wl_m"]
FLAG_COLUMNS = ["graph_id", "kind", "time_local", "value", "rule"]

RAIN_MAX_15MIN_MM = 100.0
RAIN_GAP_MIN_MM = 30.0
GAP_MIN_MISSING_MIN = 120
RAIN_CONTINUES_MM = 10.0
RAIN_STUCK_MIN_MM = 20.0
RAIN_STUCK_COUNT = 3
RAIN_STUCK_WINDOW = pd.Timedelta(hours=24)
WL_SPIKE_M = 1.0
WL_REVERT_M = 0.2
STEP = pd.Timedelta(minutes=15)


def _prev_valid_gap_min(df: pd.DataFrame, col: str) -> pd.Series:
    """Minutes between each reading and the previous non-NaN reading of the same gauge (NaN if none).
    `df` must be sorted by graph_id, time_local."""
    t = df["time_local"].where(df[col].notna())
    prev = t.groupby(df["graph_id"]).shift(1).groupby(df["graph_id"]).ffill()
    return (df["time_local"] - prev) / pd.Timedelta(minutes=1)


def _rain_masks(rf: pd.DataFrame) -> dict[str, pd.Series]:
    """Boolean masks (index of `rf`) per rain rule, before precedence is applied."""
    r = rf["rain_15min_mm"]
    gap = _prev_valid_gap_min(rf, "rain_15min_mm")
    nxt = r.groupby(rf["graph_id"]).shift(-1)
    continues = (nxt >= RAIN_CONTINUES_MM) & ((rf["time_local"].groupby(rf["graph_id"]).shift(-1) - rf["time_local"]) <= 2 * STEP)
    masks = {
        "rain_negative": r < 0,
        "rain_implausible": r > RAIN_MAX_15MIN_MM,
        "rain_after_gap": (r >= RAIN_GAP_MIN_MM) & (gap - STEP / pd.Timedelta(minutes=1) >= GAP_MIN_MISSING_MIN)
        & ~continues,
    }
    stuck = pd.Series(False, index=rf.index)
    cand = rf[r >= RAIN_STUCK_MIN_MM].sort_values(["graph_id", "rain_15min_mm", "time_local"])
    if len(cand) >= RAIN_STUCK_COUNT:
        key = cand["graph_id"].astype(str) + "|" + cand["rain_15min_mm"].astype(str)
        t = cand["time_local"]
        same = key.eq(key.shift(-(RAIN_STUCK_COUNT - 1))).to_numpy()
        close = ((t.shift(-(RAIN_STUCK_COUNT - 1)) - t) <= RAIN_STUCK_WINDOW).to_numpy()
        start = np.flatnonzero(same & close)
        pos = np.unique(np.concatenate([start + k for k in range(RAIN_STUCK_COUNT)])) if len(start) else []
        stuck.loc[cand.index[pos]] = True
    masks["rain_stuck"] = stuck
    return masks


def _wl_spike_mask(wl: pd.DataFrame) -> pd.Series:
    """A reading that jumps > WL_SPIKE_M from the previous reading and is followed by a reading back
    within WL_REVERT_M of that previous value. Neighbours must be within 2 steps in time."""
    g = wl["graph_id"]
    v = wl["wl_m"]
    prev, nxt = v.groupby(g).shift(1), v.groupby(g).shift(-1)
    t = wl["time_local"]
    near_prev = (t - t.groupby(g).shift(1)) <= 2 * STEP
    near_next = (t.groupby(g).shift(-1) - t) <= 2 * STEP
    return (near_prev & near_next & ((v - prev).abs() > WL_SPIKE_M) & ((nxt - prev).abs() <= WL_REVERT_M)).fillna(False)


def clean_readings(readings: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (clean, flags). Bad values become NaN (never 0); `flags` lists what was removed.

    Row order is preserved and the index is reset. NaN readings are kept (they mean "no data")."""
    empty_flags = pd.DataFrame(columns=FLAG_COLUMNS)
    if readings.empty:
        return readings.copy(), empty_flags
    readings = readings.reset_index(drop=True)
    clean = readings.copy()
    flag_parts = []

    def _collect(sub: pd.DataFrame, masks: dict[str, pd.Series], col: str) -> None:
        taken = pd.Series(False, index=sub.index)
        for rule, mask in masks.items():
            hit = mask.fillna(False) & ~taken
            taken |= hit
            if hit.any():
                flag_parts.append(pd.DataFrame({"graph_id": sub.loc[hit, "graph_id"], "kind": sub.loc[hit, "kind"],
                                                "time_local": sub.loc[hit, "time_local"], "value": sub.loc[hit, col],
                                                "rule": rule}))
        clean.loc[taken[taken].index, col] = np.nan

    rf = readings[readings["kind"] == "rf"].sort_values(["graph_id", "time_local"])
    if not rf.empty:
        _collect(rf, _rain_masks(rf), "rain_15min_mm")
    wl = readings[readings["kind"] == "wl"].sort_values(["graph_id", "time_local"])
    if not wl.empty:
        _collect(wl, {"wl_spike": _wl_spike_mask(wl)}, "wl_m")

    flags = pd.concat(flag_parts, ignore_index=True)[FLAG_COLUMNS] if flag_parts else empty_flags
    return clean, flags.sort_values(["graph_id", "time_local"]).reset_index(drop=True) if len(flags) else flags
