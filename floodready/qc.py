"""Quality control for JPS 15-min readings (improvements #2, rain and river-level QC).

JPS rain is a cumulative counter that the loaders difference to 15-min values, so a data gap,
a stuck counter or the 1 Jan reset produce impossible values (-3,275 to +2,050 mm per 15 min).
`clean_readings` turns the bad values into NaN (never 0) and returns what it removed, so every
consumer (rules, ML features, API) sees the same clean data and every removal is auditable.

Rules, applied in this order (a reading is flagged by the first rule that matches).
Thresholds and the evidence for them are in docs/data-qc-report.md (regenerate with scripts/qc_report.py).

rain_negative       rain < 0. A counter cannot go down; these are resets (1 Jan, gauge restarts).
rain_implausible    rain > RAIN_MAX_15MIN_MM (100 mm per 15 min = 400 mm/h).
rain_counter_rebound  a positive reading within 24 h after a negative one (<= -REBOUND_MIN_DIP_MM) at the
                    same gauge whose value matches the dip (within max(1 mm, 5 %)): the counter dipped and
                    was restored, so the restore is a fake burst, not rain.
rain_after_gap      rain >= RAIN_GAP_MIN_MM in the first reading after >= GAP_MIN_MISSING_MIN of missing
                    readings, unless the next reading is >= RAIN_CONTINUES_MM and differs from it (a storm
                    that began during the gap keeps raining; an identical repeat is a duplicated catch-up).
rain_stuck          the same value >= RAIN_STUCK_MIN_MM at least 3 times within 24 h at one gauge.
wl_spike            a river level more than WL_SPIKE_M away from BOTH neighbours, in the same direction, while
                    the neighbours are close to each other (|next - prev| <= max(WL_REVERT_M, 0.5 * |jump|)).
                    Works on a rising or falling river. Negative levels are valid (tidal stations' datum is
                    below sea level); only a single-reading excursion is flagged.
wl_unresponsive     a river level that stayed within WL_FLAT_M for 4.5 h (the 3 h rain window plus the fixed 90 min
                    response lag, WL_RESPONSE_LAG_MIN) while at least TWO rain gauges within WL_RAIN_RADIUS_KM of
                    the station (the second-wettest gauge's rolling 3 h sum, after rain QC) each totalled >= WL_RAIN_MM
                    in the 3 h window that ended 90 min before the reading, so the river had 90 min to answer that
                    rain. One wet gauge is not enough: a single local cell over one gauge is not evidence that the
                    catchment got wet (gauges are 5-9 km apart; the same two-gauge rule as street warnings). A flat
                    level alone is base flow (Sg. Binjai at Pekan Meru stays flat for 6 h in 91 % of its readings);
                    flat during widespread heavy rain is a gauge that has stopped responding (Kg. Perepat, 26558,
                    12 Nov 2024). Flagged from the reading where the condition is first met until the level moves
                    (> WL_FLAT_M from the flat level); the run continues over missing readings (a level that is
                    still in the band after a gap is the same run; one that has moved ends it). Readings of the run
                    before the first detection are not flagged (no look-back). Re-entry: when a run ends because a
                    reading left the band, and the level is back within the band of the run's value within
                    WL_RUN_REENTRY_READINGS (4) readings (and below alert), flagging resumes from that reading (the
                    stray reading itself is kept). A stuck gauge jitters by a few cm now and then; without this each
                    jitter ended the run and a new two-gauge storm was needed. Causal. Needs `stations`
                    (coordinates); skipped without it.
                    Dead-gauge state (station level): a gauge that did not respond to WL_DEAD_EVENTS (2) qualifying
                    storms within WL_DEAD_WINDOW_DAYS (30), at least WL_DEAD_EVENTS_APART_H (48 h) apart, is DEAD from
                    the moment the second storm's response window closes, and every reading below its alert level is
                    flagged until it responds again. A qualifying storm: the second-wettest gauge within
                    WL_RAIN_RADIUS_KM AND the gauge nearest to the station both reach WL_RAIN_MM in 3 h (so the storm
                    is over the station: without this, Pekan Meru, 3115084_ and 26039 were called dead after cells
                    that rained on a neighbouring catchment). No response: the 3-reading-median level's range within
                    WL_DEAD_RESPONSE_HOURS (8 h) of the storm is < WL_DEAD_NO_RESPONSE_M (0.10 m); the median keeps a
                    one-reading glitch from counting as a response. If another river station within WL_DEAD_NEIGHBOUR_KM (15 km)
                    has data in that window, at least one of them must have moved >= WL_DEAD_NEIGHBOUR_RISE_M (0.3 m)
                    (otherwise a dry catchment would be called dead); with no such station the gauge's own misses
                    decide. A tidal neighbour (lag-25 autocorrelation < -0.2, the test of ml.evaluate.tidal_stations)
                    never counts, because the tide alone moves it by 0.3 m or more in nearly every 8 h window. Excluding
                    them was chosen over a tuned alternative (de-tiding by differencing was tried: it changed no flag
                    on the archive and a tidal station still moved 0.3 m in 89 % of dry windows); the cost is that
                    26558, whose corroboration came largely from tidal stations, is flagged 87 % rather than 90 %. A storm the gauge answers resets the count and the
                    probation. DEAD ends when the 3-reading-median level rises or falls by >= WL_DEAD_EXIT_RISE_M
                    (0.2 m) within 8 h (any real movement means the gauge is alive), or any reading reaches the alert level; that reading is kept (the median makes a
                    revived gauge leave DEAD one reading late: its first rising reading below alert is still blanked).
                    Probation: after DEAD ends, ONE unanswered qualifying storm within WL_DEAD_PROBATION_DAYS (30)
                    puts the gauge back (a gauge that glitched or jumped to a new stuck level is still dead).
                    The nearest-gauge condition, the 48 h separation and the median were added after looking at the
                    archive, not before: without the nearest-gauge condition 3115084_ (800 readings) and 26039 (593)
                    were called dead after cells over neighbouring catchments, and Pekan Meru lost the start of its
                    27 Feb 2025 rise in an earlier version; without the median 26558 drops from 87 % to 70 % because
                    one-reading dips count as responses. The 48 h condition changes nothing on this archive. Evidence: Kg. Perepat (26558) is a dead sensor (stuck -0.78 m, then 0.36 m since 22 Nov
                    2024) that ~60 storms moved by <= 0.08 m while neighbouring stations rose 0.6-1.6 m.
                    Not flagged (the value is kept), because there is no evidence either way: a station with fewer
                    than two rain gauges within the radius (the rule cannot check it; a gauge stuck low there reports
                    "normal" unnoticed, so such stations should be listed as unchecked); a station whose stations-table
                    thresholds are untrusted (`thresholds_ok` False) or that has no alert level (dead state only: the
                    run rule treats an unknown alert as "rule applies" when the table has no `thresholds_ok`
                    column). Alarm guard: nothing at or above wl_alert_m is ever flagged (a gauge stuck high or a
                    plateau in a flood keeps its value; a run also ends if the level reaches alert).
                    Flagged values become NaN. Downstream: the rule engine forward-fills a level for 2 h, so
                    staleness starts after that; the township's river rule then has no reading from that station and
                    its confidence is low only if no township station reports. ML features have no forward-fill and
                    lose the readings at once. A false flag can therefore hide a rising river, hence the guards above.
rain_monthly_implausible  a gauge whose rolling 30-day rain total (after the rules above) is > RAIN_MONTH_MIN_MM and
                    > RAIN_MONTH_RATIO times the median 30-day total of its neighbours (gauges within
                    RAIN_MONTH_RADIUS_KM; at least RAIN_MONTH_MIN_NEIGHBOURS of them, each with data in at least
                    RAIN_MONTH_MIN_COVERAGE (80 %) of the window, so a gappy neighbour is left out rather than
                    counted as dry). Catches a gauge that reads far too much for weeks (26405, May 2024: about
                    2,100 mm in a month) without single readings being implausible. The same test on the last 7 days
                    (floor scaled to 7 days) must also hold, so flagging ends within a week of the fault ending
                    instead of lasting until the bad readings leave the 30-day window. Causal: a reading is
                    flagged when the totals ending at it pass the test, so the weeks before the 30-day total crossed
                    the limit are kept (a live system cannot know yet). Zero readings are kept (a gauge that reads
                    too high still reads a true zero in the dry). A wet month everywhere (neighbours as wet) is not
                    flagged. Needs `stations`; skipped without it. A gauge with no coordinates in the lookup (the
                    DBKL "(F2)" gauges, including 26405: the frozen data.gov.my list has none and the Infobanjir live
                    tables carry no coordinates) is compared with the other gauges of its district instead, if the
                    table has a `district` column and the district's gauges that have coordinates span at most
                    RAIN_MONTH_DISTRICT_MAX_SPAN_KM (25 km; the span is logged at INFO); no coordinates are invented.

Live mode: wl_spike and rain_after_gap need the NEXT reading. When a gauge's latest reading has no
next reading yet, it is KEPT and judged when the next one arrives (a real rise or storm after an outage
must not be hidden). The archive cleaning therefore sees t+15 min, while live cleaning does not: a small
train/serve difference (about 100 readings in 8 M).

Live vs replay: a flat run lasts until the level moves, so whether a long run is flagged depends on how
much history is loaded. Archive cleaning sees the whole history; live cleaning sees only the live files
(since - 1 day), so a stuck gauge whose heavy rain fell before that window is not flagged live. Live rows
override archive rows in the runner. Not fixed (follow-up: run QC over archive + live together).
The dead-gauge state and the monthly rain rule have the same property: live flags a long-dead gauge only if
two unanswered storms (or one, on probation) fall inside the history it loads (QC_HISTORY_DAYS), so live flags
less than the archive. Train/serve gap until PR #32 sizes the live tail from QC_HISTORY_DAYS.

Precondition: one row per (graph_id, kind, time_local); the loaders de-duplicate.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

COLUMNS = ["graph_id", "kind", "time_local", "rain_15min_mm", "wl_m"]
FLAG_COLUMNS = ["graph_id", "kind", "time_local", "value", "rule"]

RAIN_MAX_15MIN_MM = 100.0
RAIN_GAP_MIN_MM = 30.0
GAP_MIN_MISSING_MIN = 120
RAIN_CONTINUES_MM = 10.0
REBOUND_MIN_DIP_MM = 5.0
REBOUND_WINDOW = pd.Timedelta(hours=24)
RAIN_STUCK_MIN_MM = 20.0
RAIN_STUCK_COUNT = 3
RAIN_STUCK_WINDOW = pd.Timedelta(hours=24)
WL_SPIKE_M = 1.0
WL_REVERT_M = 0.2
WL_FLAT_M = 0.015
WL_FLAT_HOURS = 3
WL_RESPONSE_LAG_MIN = 90           # the river may answer rain this late: the rain window ends this long before the reading
WL_FLAT_MIN_FRAC = 11 / 13         # share of the flat window's readings that must be valid (tolerates short gaps)
WL_RAIN_MM = 30.0
WL_RAIN_RADIUS_KM = 10.0
WL_RUN_REENTRY_READINGS = 4        # a run that ended on one stray reading resumes if the level is back in its band within this many readings
WL_MIN_RAIN_GAUGES = 2             # gauges that must each reach WL_RAIN_MM (the second-wettest gauge decides)
# Dead-gauge state numbers, pre-stated in the PR before they were measured on the archive.
WL_DEAD_EVENTS = 2                 # qualifying storms with no response ...
WL_DEAD_WINDOW_DAYS = 30           # ... within this many days make the gauge DEAD
WL_DEAD_EVENT_SEPARATION_H = 6     # storms at least this far apart are separate events
WL_DEAD_EVENTS_APART_H = 48        # counted storms must be this far apart (two cells of one weather system that missed the catchment are one miss)
WL_DEAD_RESPONSE_HOURS = 8        # the response window after a storm starts (also the exit look-back)
WL_DEAD_NO_RESPONSE_M = 0.10       # range of the level in that window below this = no response
WL_DEAD_NEIGHBOUR_KM = 15.0        # another river station this close must have responded ...
WL_DEAD_NEIGHBOUR_RISE_M = 0.3     # ... by at least this much (range in the window)
WL_DEAD_EXIT_RISE_M = 0.2          # a rise of this much within 8 h ends DEAD
WL_TIDAL_LAG = 25                  # quarter hours (6.25 h) for the tidal-station test
WL_TIDAL_AUTOCORR = -0.2
WL_DEAD_PROBATION_DAYS = 30        # after DEAD ends, one unanswered qualifying storm within this many days puts the gauge back
WL_DEAD_MIN_VALID_FRAC = 0.5      # share of the response window's readings that must exist for the event to be judged
RAIN_MONTH_STEPS = 30 * 96         # 30 days of 15-min readings
RAIN_MONTH_SHORT_STEPS = 7 * 96    # the short window that ends the flagged state
RAIN_MONTH_MIN_MM = 600.0          # chosen before looking at 12 Nov 2024; see docs/data-qc-report.md
RAIN_MONTH_RATIO = 3.0
RAIN_MONTH_RADIUS_KM = 10.0
RAIN_MONTH_MIN_NEIGHBOURS = 2
RAIN_MONTH_DISTRICT_MAX_SPAN_KM = 25.0   # district fallback only where the district's gauges with coordinates span this much or less
RAIN_MONTH_MIN_COVERAGE = 0.8     # a neighbour counts only if it has data in this share of the window
# Longest look-back any rule needs: a stuck run can reach 32 days, the monthly rain window is 30 days (+ margin).
# Live mode (PR #32, fix/qc-live-archive-tail) sizes the archive tail it loads before `since` from this constant.
QC_HISTORY_DAYS = 40
STEP = pd.Timedelta(minutes=15)


def _prev_valid_gap_min(df: pd.DataFrame, col: str) -> pd.Series:
    """Minutes between each reading and the previous non-NaN reading of the same gauge (NaN if none).
    `df` must be sorted by graph_id, time_local."""
    t = df["time_local"].where(df[col].notna())
    prev = t.groupby(df["graph_id"]).shift(1).groupby(df["graph_id"]).ffill()
    return (df["time_local"] - prev) / pd.Timedelta(minutes=1)


def _rebound_mask(rf: pd.DataFrame) -> pd.Series:
    """Positive readings that restore a preceding counter dip (see module docstring)."""
    out = pd.Series(False, index=rf.index)
    neg = rf[rf["rain_15min_mm"] <= -REBOUND_MIN_DIP_MM]
    for gid, dips in neg.groupby("graph_id"):
        g = rf[(rf["graph_id"] == gid) & (rf["rain_15min_mm"] > 0)]
        for row in dips.itertuples():
            dip = -row.rain_15min_mm
            win = g[(g["time_local"] > row.time_local) & (g["time_local"] <= row.time_local + REBOUND_WINDOW)]
            match = win[(win["rain_15min_mm"] - dip).abs() <= max(1.0, 0.05 * dip)]
            if len(match):
                out.loc[match.index[0]] = True
    return out


def _rain_masks(rf: pd.DataFrame, stations: pd.DataFrame | None = None) -> dict[str, pd.Series]:
    """Boolean masks (index of `rf`) per rain rule, before precedence is applied."""
    r = rf["rain_15min_mm"]
    gap = _prev_valid_gap_min(rf, "rain_15min_mm")
    g = rf["graph_id"]
    nxt = r.groupby(g).shift(-1)
    next_t = rf["time_local"].groupby(g).shift(-1)
    continues = (nxt >= RAIN_CONTINUES_MM) & (nxt != r) & ((next_t - rf["time_local"]) <= 2 * STEP)
    pending = next_t.isna()          # latest reading of the gauge: judged when the next one arrives
    after_gap = (r >= RAIN_GAP_MIN_MM) & (gap - STEP / pd.Timedelta(minutes=1) >= GAP_MIN_MISSING_MIN) & ~continues & ~pending
    masks = {
        "rain_negative": r < 0,
        "rain_implausible": r > RAIN_MAX_15MIN_MM,
        "rain_counter_rebound": _rebound_mask(rf),
        # the catch-up, and an identical repeat right after it (a duplicated catch-up)
        "rain_after_gap": after_gap | (after_gap.groupby(g).shift(1, fill_value=False) & (r == r.groupby(g).shift(1))),
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
    prior = pd.concat(list(masks.values()), axis=1).any(axis=1)
    masks["rain_monthly_implausible"] = _rain_monthly_mask(rf, r.where(~prior), stations)
    return masks


def _rain_monthly_mask(rf: pd.DataFrame, rain: pd.Series, stations: pd.DataFrame | None) -> pd.Series:
    """Readings at a gauge whose rolling 30-day total is implausibly high against its neighbours (see module docstring).
    `rain` is the rain after the earlier rules (NaN where removed). Returns a mask on rf's index."""
    out = pd.Series(False, index=rf.index)
    if stations is None or stations.empty or not {"graph_id", "kind", "lat", "lon"} <= set(stations.columns):
        return out
    rfs = stations[stations.kind == "rf"].assign(graph_id=lambda d: d.graph_id.astype(str)).drop_duplicates("graph_id").set_index("graph_id")
    xy = rfs.dropna(subset=["lat", "lon"])[["lat", "lon"]]
    district = rfs["district"].dropna() if "district" in rfs.columns else pd.Series(dtype=object)
    d = rf[["graph_id", "time_local"]].assign(graph_id=rf["graph_id"].astype(str), v=rain.to_numpy())
    d = d.drop_duplicates(["graph_id", "time_local"], keep="last")
    p = d.pivot(index="time_local", columns="graph_id", values="v")
    p = p.reindex(pd.date_range(p.index.min(), p.index.max(), freq=STEP))
    elapsed = np.arange(1, len(p) + 1)[:, None]

    def window(n):
        total = p.fillna(0.0).rolling(n, min_periods=1).sum()
        covered = p.notna().rolling(n, min_periods=1).sum() >= RAIN_MONTH_MIN_COVERAGE * np.minimum(elapsed, n)
        return total, covered

    total, covered = window(RAIN_MONTH_STEPS)
    short, short_covered = window(RAIN_MONTH_SHORT_STEPS)

    def implausible(gid, nb, tot, cov, floor):
        nb_tot = tot[nb].where(cov[nb])                       # a neighbour short of data is left out, never counted as dry
        enough = nb_tot.notna().sum(axis=1) >= RAIN_MONTH_MIN_NEIGHBOURS
        return (tot[gid] > floor) & (tot[gid] > RAIN_MONTH_RATIO * nb_tot.median(axis=1)) & enough

    for gid in total.columns[(total > RAIN_MONTH_MIN_MM).any()]:
        if gid in xy.index:
            dist = _haversine_km(xy.at[gid, "lat"], xy.at[gid, "lon"], xy["lat"].to_numpy(), xy["lon"].to_numpy())
            nb = [g for g, km in zip(xy.index, dist) if g != gid and km <= RAIN_MONTH_RADIUS_KM and g in total.columns]
        elif gid in district.index:                           # no coordinates in the lookup: compare with the gauges of its district
            peers = district.index[district == district[gid]]
            at = xy.loc[xy.index.intersection(peers)]
            span = max((float(_haversine_km(a.lat, a.lon, at.lat.to_numpy(), at.lon.to_numpy()).max()) for a in at.itertuples()), default=np.inf)
            logging.getLogger(__name__).info("rain_monthly_implausible: %s has no coordinates, district %s spans %.1f km (limit %g km)",
                                             gid, district[gid], span, RAIN_MONTH_DISTRICT_MAX_SPAN_KM)
            if span > RAIN_MONTH_DISTRICT_MAX_SPAN_KM:              # a district that large is not one rain climate: skip
                continue
            nb = [g for g in peers if g != gid and g in total.columns]
        else:
            continue
        if len(nb) < RAIN_MONTH_MIN_NEIGHBOURS:
            continue
        bad = (implausible(gid, nb, total, covered, RAIN_MONTH_MIN_MM)
               & implausible(gid, nb, short, short_covered, RAIN_MONTH_MIN_MM * RAIN_MONTH_SHORT_STEPS / RAIN_MONTH_STEPS))
        if bad.any():
            out |= (rf["graph_id"].astype(str) == gid) & (rain > 0) & rf["time_local"].map(bad).fillna(False).astype(bool)
    return out


def _wl_spike_mask(wl: pd.DataFrame) -> pd.Series:
    """Single-reading excursion: > WL_SPIKE_M from both neighbours, same direction, neighbours close to each other.
    Neighbours must be within 2 steps in time. A gauge's latest reading (no next) is never flagged."""
    g = wl["graph_id"]
    v = wl["wl_m"]
    prev, nxt = v.groupby(g).shift(1), v.groupby(g).shift(-1)
    t = wl["time_local"]
    near = ((t - t.groupby(g).shift(1)) <= 2 * STEP) & ((t.groupby(g).shift(-1) - t) <= 2 * STEP)
    d1, d2 = v - prev, v - nxt
    return (near & (d1.abs() > WL_SPIKE_M) & (d2.abs() > WL_SPIKE_M) & (np.sign(d1) == np.sign(d2))
            & ((nxt - prev).abs() <= np.maximum(WL_REVERT_M, 0.5 * d1.abs()))).fillna(False)


def _haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0088 * np.arcsin(np.sqrt(a))


def _wl_unresponsive_mask(wl: pd.DataFrame, rain: pd.DataFrame, stations: pd.DataFrame | None) -> pd.Series:
    """Flat river level during heavy rain nearby (see module docstring). `wl` sorted by graph_id, time_local;
    `rain` is the rain QC'd rf rows. Returns a mask on wl's index."""
    out = pd.Series(False, index=wl.index)
    if stations is None or stations.empty or rain.empty or not {"graph_id", "kind", "lat", "lon"} <= set(stations.columns):
        return out
    st = stations.dropna(subset=["lat", "lon"]).assign(graph_id=lambda d: d.graph_id.astype(str))
    wl_xy = st[st.kind == "wl"].drop_duplicates("graph_id").set_index("graph_id")[["lat", "lon"]]
    rf_xy = st[st.kind == "rf"].drop_duplicates("graph_id").set_index("graph_id")[["lat", "lon"]]
    rf_xy = rf_xy[rf_xy.index.isin(rain["graph_id"].astype(str).unique())]
    if wl_xy.empty or rf_xy.empty:
        return out
    n_win = int(WL_FLAT_HOURS * 4)                          # rain window, 12 readings
    lag = WL_RESPONSE_LAG_MIN // 15                         # 6 readings
    n_flat = n_win + lag                                    # flat window: 18 steps = 4.5 h, 19 readings
    min_valid = int(np.ceil(WL_FLAT_MIN_FRAC * (n_flat + 1)))
    lv_by = {str(k): x.drop_duplicates("time_local", keep="last").set_index("time_local")["wl_m"] for k, x in wl.groupby("graph_id")}
    alert = (st[st.kind == "wl"].drop_duplicates("graph_id").set_index("graph_id")["wl_alert_m"]
             if "wl_alert_m" in st.columns else pd.Series(dtype=float))
    thresholds_ok = (st[st.kind == "wl"].drop_duplicates("graph_id").set_index("graph_id")["thresholds_ok"]
                     .map(lambda x: x is True or x is np.True_).to_dict() if "thresholds_ok" in st.columns else {})
    rain_by_gauge = {gid: g for gid, g in rain.groupby(rain["graph_id"].astype(str))}
    for gid, g in wl.groupby("graph_id"):
        gid = str(gid)
        if gid not in wl_xy.index:
            continue
        d = _haversine_km(wl_xy.at[gid, "lat"], wl_xy.at[gid, "lon"], rf_xy["lat"].to_numpy(), rf_xy["lon"].to_numpy())
        near = rf_xy.index[d <= WL_RAIN_RADIUS_KM]
        if len(near) < WL_MIN_RAIN_GAUGES or g["wl_m"].notna().sum() < min_valid:
            continue                                        # not checked: one gauge cannot corroborate itself, and too little data
        if "thresholds_ok" in st.columns and thresholds_ok.get(gid) is not True:
            continue                                        # untrusted or missing thresholds: do not compare to them
        grid = pd.date_range(g["time_local"].min(), g["time_local"].max(), freq=STEP)
        lvl = g.drop_duplicates("time_local", keep="last").set_index("time_local")["wl_m"].reindex(grid)
        sums = pd.DataFrame({r: rain_by_gauge[r].drop_duplicates("time_local", keep="last").set_index("time_local")["rain_15min_mm"]
                             .reindex(grid).fillna(0.0) if r in rain_by_gauge else pd.Series(0.0, index=grid) for r in near}
                            ).rolling(n_win, min_periods=1).sum()
        rain_sum = pd.Series(-np.sort(-sums.to_numpy(), axis=1)[:, WL_MIN_RAIN_GAUGES - 1], index=grid)   # the 2nd-wettest gauge
        rain_lagged = rain_sum.shift(lag, fill_value=0.0)    # rain in the 3 h that ended 90 min before each reading
        roll = lvl.rolling(n_flat + 1, min_periods=min_valid)
        flat = ((roll.max() - roll.min()) <= WL_FLAT_M + 1e-9).to_numpy()
        cand = np.flatnonzero(flat & (rain_lagged.to_numpy() >= WL_RAIN_MM))
        alert_m = float(alert.get(gid, np.nan))
        if "thresholds_ok" in st.columns and not np.isfinite(alert_m):
            continue                                        # thresholds_ok but no alert level: cannot apply the guard, so do not flag
        v = lvl.to_numpy()
        hit = np.zeros(len(v), dtype=bool)
        band = WL_FLAT_M + 1e-9
        i_next = 0
        for i in cand:
            if i < i_next:
                continue
            ref = float(np.nanmedian(v[max(0, i - n_flat): i + 1]))
            if ref >= alert_m:                                # NaN alert: unknown, rule applies
                continue                                      # stuck high or plateau in a flood: keep the value
            start = i
            while True:
                stop = (np.abs(v[start:] - ref) > band) | (v[start:] >= alert_m)     # NaN compares False: gaps do not end a run
                moved = np.flatnonzero(stop)
                end = start + moved[0] if len(moved) else len(v)
                hit[start:end] = True
                if end >= len(v) or v[end] >= alert_m:
                    break
                back = [j for j in range(end + 1, min(end + 1 + WL_RUN_REENTRY_READINGS, len(v)))
                        if abs(v[j] - ref) <= band and not v[j] >= alert_m]  # NaN readings and an unknown alert compare False
                if not back:
                    break
                start = back[0]                               # the stray reading(s) before it stay kept; the run goes on
            i_next = end
        if np.isfinite(alert_m):
            neighbours = [lv_by[n].reindex(grid).to_numpy() for n in wl_xy.index
                          if n != gid and n in lv_by and _haversine_km(wl_xy.at[gid, "lat"], wl_xy.at[gid, "lon"],
                                                                       wl_xy.at[n, "lat"], wl_xy.at[n, "lon"]) <= WL_DEAD_NEIGHBOUR_KM]
            neighbours = [n for n in neighbours if not _is_tidal(n)]      # the tide alone moves a tidal station: it never corroborates
            closest = near[int(np.argmin(d[d <= WL_RAIN_RADIUS_KM]))]               # the rain gauge nearest to the station
            over_station = np.minimum(rain_sum.to_numpy(), sums[closest].to_numpy())    # the storm is over the station, not a cell in the next catchment
            hit |= _dead_gauge_hits(lvl, over_station, alert_m, neighbours)
        out.loc[g.index] = pd.Series(hit, index=grid).reindex(g["time_local"]).to_numpy() & g["wl_m"].notna().to_numpy()
    return out


def _is_tidal(level: np.ndarray) -> bool:
    """A station whose level follows the tide: autocorrelation at 6.25 h (half a tidal cycle) below -0.2, the same test as
    floodready.ml.evaluate.tidal_stations. Needs two days of data. Uses the whole loaded series: a slow station property."""
    s = pd.Series(level)
    return bool(s.notna().sum() >= 2 * 96 and s.autocorr(WL_TIDAL_LAG) < WL_TIDAL_AUTOCORR)


def _dead_gauge_hits(lvl: pd.Series, storm_mm: np.ndarray, alert_m: float, neighbours: list[np.ndarray]) -> np.ndarray:
    """Readings flagged while the gauge is in the DEAD state (see module docstring). `storm_mm`: the second-wettest
    gauge's rolling 3 h rain per grid step; `neighbours`: level arrays of the river stations within WL_DEAD_NEIGHBOUR_KM
    on the same grid. Causal: a storm is judged WL_DEAD_RESPONSE_HOURS after it started, with data up to then."""
    v = lvl.to_numpy()
    hit = np.zeros(len(v), dtype=bool)
    w = WL_DEAD_RESPONSE_HOURS * 4                                  # 32 steps, 33 readings in the window
    need = WL_DEAD_MIN_VALID_FRAC * (w + 1)
    eps = 1e-9

    def smooth(x):                                                  # 3-reading median: a one-reading dip is a glitch, not a response
        return pd.Series(x).rolling(3, min_periods=2).median().to_numpy()

    def moved(x, a, b):
        seg = x[a:b + 1]
        return (np.nanmax(seg) - np.nanmin(seg)) if np.isfinite(seg).sum() >= need else np.nan

    events, last = [], -10 ** 9
    for i in np.flatnonzero(storm_mm >= WL_RAIN_MM):
        if i - last > WL_DEAD_EVENT_SEPARATION_H * 4:
            events.append(i)
        last = i
    fv = smooth(v)
    neighbours = [smooth(n) for n in neighbours]
    fs = pd.Series(fv)
    rise = (fs - fs.rolling(w + 1, min_periods=1).min()).to_numpy()
    fall = (fs.rolling(w + 1, min_periods=1).max() - fs).to_numpy()
    leave = (rise >= WL_DEAD_EXIT_RISE_M - eps) | (fall >= WL_DEAD_EXIT_RISE_M - eps) | (v >= alert_m)     # an alert-level reading always ends DEAD (raw value)
    unresponsive, dead_until, last_exit = [], -1, -10 ** 9
    for onset in events:
        judged = onset + w                                          # the window has closed: all data <= judged
        if judged >= len(v) or judged <= dead_until:
            continue
        own = moved(fv, onset, judged)
        if np.isnan(own):
            continue
        if own >= WL_DEAD_NO_RESPONSE_M or np.nanmax(v[onset:judged + 1]) >= alert_m:
            unresponsive, last_exit = [], -10 ** 9                  # it answered a storm: the count and the probation start again
            continue
        others = [m for m in (moved(n, onset, judged) for n in neighbours) if not np.isnan(m)]
        if others and max(others) < WL_DEAD_NEIGHBOUR_RISE_M:
            continue                                                # nobody responded: a dry catchment, not evidence
        probation = judged - last_exit <= WL_DEAD_PROBATION_DAYS * 96     # it was dead a short while ago: one more miss is enough
        if not probation:
            unresponsive = [e for e in unresponsive if judged - e <= WL_DEAD_WINDOW_DAYS * 96]
            if unresponsive and judged - unresponsive[-1] < WL_DEAD_EVENTS_APART_H * 4:
                continue                                            # the same weather system: one miss, not two
            unresponsive.append(judged)
        if probation or len(unresponsive) >= WL_DEAD_EVENTS:
            gone = np.flatnonzero(leave[judged:])
            dead_until = judged + int(gone[0]) if len(gone) else len(v)
            hit[judged:dead_until] = v[judged:dead_until] < alert_m  # NaN compares False
            unresponsive, last_exit = [], dead_until
    return hit


def clean_readings(readings: pd.DataFrame, stations: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (clean, flags). Bad values become NaN (never 0); `flags` lists what was removed.

    `stations` (graph_id, kind, lat, lon; floodready.stations.load_default()) enables the rules that need
    coordinates (wl_unresponsive). Without it they are skipped.

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
        _collect(rf, _rain_masks(rf, stations), "rain_15min_mm")
    wl = readings[readings["kind"] == "wl"].sort_values(["graph_id", "time_local"])
    if not wl.empty:
        rf_clean = clean[clean["kind"] == "rf"]
        spike = _wl_spike_mask(wl)
        # a spike must not pose as a response (dead-gauge corroboration) or break a flat run: judge on the level without it
        wl_ok = wl.assign(wl_m=wl["wl_m"].where(~spike))
        _collect(wl, {"wl_spike": spike, "wl_unresponsive": _wl_unresponsive_mask(wl_ok, rf_clean, stations)}, "wl_m")

    flags = pd.concat(flag_parts, ignore_index=True)[FLAG_COLUMNS] if flag_parts else empty_flags
    return clean, flags.sort_values(["graph_id", "time_local"]).reset_index(drop=True) if len(flags) else flags
