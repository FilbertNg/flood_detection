"""Data QC report on the JPS history archive and the tide series → docs/data-qc-report.md.

Usage: python scripts/qc_report.py
Re-run it whenever the archive grows (scripts/archive_jps_history.py); the report states the date.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from floodready import qc, tide  # noqa: E402

HIST = ROOT / "data" / "raw" / "jps_hist"
OUT = ROOT / "docs" / "data-qc-report.md"
STORM = (pd.Timestamp("2024-11-12 06:00"), pd.Timestamp("2024-11-12 12:00"))

RULE_TEXT = {
    "rain_negative": "rain < 0 (a counter cannot go down: 1 Jan reset, gauge restart)",
    "rain_implausible": f"rain > {qc.RAIN_MAX_15MIN_MM:g} mm per 15 min (> {4 * qc.RAIN_MAX_15MIN_MM:g} mm/h)",
    "rain_counter_rebound": (f"a positive reading within 24 h after a dip of <= -{qc.REBOUND_MIN_DIP_MM:g} mm at the same gauge, "
                             "equal to the dip within max(1 mm, 5 %): the counter dipped and was restored"),
    "rain_after_gap": (f"rain >= {qc.RAIN_GAP_MIN_MM:g} mm in the first reading after >= {qc.GAP_MIN_MISSING_MIN // 60} h "
                       f"without readings, unless the next reading is >= {qc.RAIN_CONTINUES_MM:g} mm and different (a storm that "
                       "continues); an identical repeat right after is removed too. A gauge's latest reading is kept until the next arrives"),
    "rain_stuck": (f"the same value >= {qc.RAIN_STUCK_MIN_MM:g} mm at least {qc.RAIN_STUCK_COUNT} times within 24 h at one gauge "
                   "(only readings not already removed by the rules above)"),
    "wl_spike": (f"river level more than {qc.WL_SPIKE_M:g} m from both neighbours in the same direction, with the neighbours within "
                 f"max({qc.WL_REVERT_M:g} m, half the jump) of each other. A station's latest reading is kept until the next arrives"),
}


def load_archive() -> pd.DataFrame:
    frames = []
    for kind, col in (("rf", "rain_15min_mm"), ("wl", "wl_m")):
        for f in sorted((HIST / kind).glob("*.parquet")):
            d = pd.read_parquet(f, columns=["graph_id", "time_local", col])
            frames.append(pd.DataFrame({"graph_id": d.graph_id, "kind": kind, "time_local": d.time_local,
                                        "rain_15min_mm": d[col] if kind == "rf" else np.nan,
                                        "wl_m": d[col] if kind == "wl" else np.nan}))
    return pd.concat(frames, ignore_index=True)


def md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join("" if (isinstance(v, float) and np.isnan(v)) else str(v) for v in row) + " |")
    return "\n".join(lines)


def completeness(readings: pd.DataFrame, names: dict[str, str]) -> pd.DataFrame:
    rows = []
    for (kind, gid), g in readings.groupby(["kind", "graph_id"]):
        col = "rain_15min_mm" if kind == "rf" else "wl_m"
        valid = g.loc[g[col].notna(), "time_local"].sort_values()
        if valid.empty:
            rows.append({"kind": kind, "graph_id": gid, "name": names.get(gid, ""), "first": "", "last": "",
                         "valid_%": 0.0, "longest_gap_h": np.nan, "gap_start": ""})
            continue
        expected = (valid.iloc[-1] - valid.iloc[0]) / pd.Timedelta(minutes=15) + 1
        gaps = valid.diff().dropna()
        longest = gaps.max() if len(gaps) else pd.Timedelta(0)
        start = valid.iloc[gaps.argmax()] if len(gaps) else valid.iloc[0]
        rows.append({"kind": kind, "graph_id": gid, "name": names.get(gid, ""), "first": f"{valid.iloc[0]:%Y-%m-%d}",
                     "last": f"{valid.iloc[-1]:%Y-%m-%d}", "valid_%": round(100 * len(valid) / expected, 1),
                     "longest_gap_h": round(longest / pd.Timedelta(hours=1), 1), "gap_start": f"{start:%Y-%m-%d %H:%M}"})
    return pd.DataFrame(rows).sort_values(["kind", "graph_id"])


def rule_sections(flags: pd.DataFrame, names: dict[str, str]) -> list[str]:
    out = []
    for rule, text in RULE_TEXT.items():
        g = flags[flags.rule == rule].copy()
        out.append(f"### `{rule}`: {len(g)} readings, {g.graph_id.nunique()} stations\n\n{text}.\n")
        if g.empty:
            out.append("No readings flagged.\n")
            continue
        per = g.groupby("graph_id").agg(count=("value", "size"), min_value=("value", "min"), max_value=("value", "max"),
                                        first=("time_local", "min"), last=("time_local", "max")).reset_index()
        per.insert(1, "name", per.graph_id.map(names).fillna(""))
        per["first"], per["last"] = per["first"].dt.strftime("%Y-%m-%d %H:%M"), per["last"].dt.strftime("%Y-%m-%d %H:%M")
        out.append(md_table(per.sort_values("count", ascending=False)) + "\n")
        out.append("<details><summary>Every flagged reading</summary>\n")
        lst = g.assign(time_local=g.time_local.dt.strftime("%Y-%m-%d %H:%M"))[["graph_id", "time_local", "value"]]
        out.append(md_table(lst) + "\n\n</details>\n")
    return out


def false_positive_checks(readings: pd.DataFrame, clean: pd.DataFrame, flags: pd.DataFrame) -> list[str]:
    out = ["## 3. False-positive checks (do real storms survive?)\n"]
    rf = readings[(readings.kind == "rf") & readings.rain_15min_mm.notna()]
    removed = flags[flags.rule.str.startswith("rain")]
    kept = clean[(clean.kind == "rf") & clean.rain_15min_mm.notna()].nlargest(10, "rain_15min_mm")
    out.append(f"**Largest rain values kept** (all below the {qc.RAIN_MAX_15MIN_MM:g} mm limit; "
               f"{(clean.rain_15min_mm >= 60).sum()} readings >= 60 mm remain):\n")
    out.append(md_table(kept.assign(time_local=kept.time_local.dt.strftime("%Y-%m-%d %H:%M"))[["graph_id", "time_local", "rain_15min_mm"]]) + "\n")
    out.append(f"**Smallest positive rain values removed**: {removed[removed.value > 0].value.min():g} mm "
               f"(removed by `{removed[removed.value > 0].sort_values('value').iloc[0].rule}`; "
               f"`rain_after_gap` removed {int((flags.rule == 'rain_after_gap').sum())} readings, "
               f"`rain_counter_rebound` {int((flags.rule == 'rain_counter_rebound').sum())}; all listed in section 2).\n")
    # candidates the rain_after_gap continuation test spared
    g = rf.sort_values(["graph_id", "time_local"]).copy()
    g["gap_min"] = (g.time_local - g.groupby("graph_id").time_local.shift(1)) / pd.Timedelta(minutes=1)
    g["next"] = g.groupby("graph_id").rain_15min_mm.shift(-1)
    cand = g[(g.rain_15min_mm >= qc.RAIN_GAP_MIN_MM) & (g.rain_15min_mm <= qc.RAIN_MAX_15MIN_MM) & (g.gap_min - 15 >= qc.GAP_MIN_MISSING_MIN)]
    spared = cand.merge(flags[flags.rule == "rain_after_gap"][["graph_id", "time_local"]].assign(f=1), how="left",
                        on=["graph_id", "time_local"])
    spared = spared[spared.f.isna()]
    out.append(f"**`rain_after_gap` candidates spared because the storm continued** ({len(spared)}): a catch-up is a single "
               "lump followed by silence; these are followed by a different reading of >= 10 mm (or are a gauge's latest reading), so they look "
               "like a storm that began during the gap.\n")
    if len(spared):
        out.append(md_table(spared.assign(time_local=spared.time_local.dt.strftime("%Y-%m-%d %H:%M"))[
            ["graph_id", "time_local", "rain_15min_mm", "next"]].rename(columns={"next": "next_reading_mm"})) + "\n")
    imp = flags[flags.rule == "rain_implausible"]
    rep_ = imp.groupby(["graph_id", "value"]).size()
    rep_ = rep_[rep_ >= qc.RAIN_STUCK_COUNT]
    stuck_txt = "; ".join(f"{gid} repeats {val:g} mm {n} times" for (gid, val), n in rep_.items()) or "none"
    out.append(f"**`rain_stuck`** removed {int((flags.rule == 'rain_stuck').sum())} readings that no earlier rule had caught. "
               f"Repeated implausible values (already removed by `rain_implausible`): {stuck_txt}. "
               "The stuck rule is a guard for a gauge that sticks below the implausible limit.\n")
    s = STORM
    in_storm = flags[(flags.time_local >= s[0]) & (flags.time_local <= s[1])]
    out.append(f"**12 Nov 2024, 06:00-12:00:** {len(in_storm)} readings flagged at any station"
               + (f" ({', '.join(sorted(in_storm.graph_id.unique()))})" if len(in_storm) else "")
               + ". PEKANMERU river level and the rain gauges within 10 km are unchanged (regression test "
               "`tests/test_qc.py::test_12_nov_2024_storm_is_untouched`).\n")
    spikes = flags[flags.rule == "wl_spike"]
    if len(spikes):
        nb = spikes.sort_values(["graph_id", "time_local"])
        adjacent = int(((nb.graph_id == nb.graph_id.shift(1)) & ((nb.time_local - nb.time_local.shift(1)) <= pd.Timedelta(minutes=15))).sum())
        out.append(f"**`wl_spike`**: {len(spikes)} readings at {spikes.graph_id.nunique()} stations; the most are "
                   f"{spikes.graph_id.value_counts().head(3).to_dict()}. Flagged values range from {spikes.value.min():g} m to "
                   f"{spikes.value.max():g} m. {int((spikes.value < 0).sum())} flagged values are negative: each is a single-reading plunge "
                   f"below its neighbours, not a tidal swing. {adjacent} flagged reading(s) sit directly next to another flagged reading "
                   "(a burst of two or more bad readings, or a good reading between two spikes).\n")
    reb = flags[flags.rule == "rain_counter_rebound"]
    out.append(f"**`rain_counter_rebound`**: {len(reb)} readings removed after a counter dip"
               + (f", largest {reb.value.max():g} mm" if len(reb) else "") + ".\n")
    return out


def tide_section() -> list[str]:
    import build_tide
    series = build_tide.load_cached()
    filled, mask = tide.fill_gaps(series)
    new = tide.tide_features(filled, mask, fit=tide.fit_harmonics(series))
    old_max = tide.MAX_HOURS_TO_HIGH
    tide.MAX_HOURS_TO_HIGH = np.inf       # the pre-fix behaviour: no bound, gaps interpolated over 2 h only
    try:
        old = tide.tide_features(series)
    finally:
        tide.MAX_HOURS_TO_HIGH = old_max
    runs = []
    m = mask.to_numpy()
    start = None
    for i, v in enumerate(m):
        if v and start is None:
            start = i
        if (not v or i == len(m) - 1) and start is not None:
            end = i if v else i - 1
            runs.append((mask.index[start], mask.index[end], end - start + 1))
            start = None
    out = ["## 5. Tide gaps and the harmonic fill\n",
           f"Open-Meteo Marine (cached in `data/raw/tide/`) covers {series.index.min():%Y-%m-%d} to {series.index.max():%Y-%m-%d}; "
           f"{int(series.isna().sum() + (len(filled) - len(series)))} hours have no value.\n",
           md_table(pd.DataFrame([{"from": f"{a:%Y-%m-%d %H:%M}", "to": f"{b:%Y-%m-%d %H:%M}", "hours": n} for a, b, n in runs])) + "\n",
           f"Missing hours are filled with a least-squares harmonic fit (mean + {', '.join(tide.CONSTITUENTS_DEG_PER_H)}) to the "
           f"{int(series.notna().sum())} observed hours and marked `tide_filled`. Observed hours are never changed.\n",
           f"High-water times (`hours_to_high_tide`) now come from the fit evaluated every {tide.SUBHOURLY_STEP_MIN} min and shifted "
           f"{tide.TIDE_PHASE_SHIFT_MIN:+.0f} min later, because Open-Meteo's highs are early against independent data "
           "(UHSLC Port Kelang gauge median -35 min, official forecasts -48 min, tide-forecast.com -38 min; see `docs/tide-check.md`). "
           "`tide_height_m` is unchanged (not shifted, not rescaled).\n",
           "**Before / after** (`hours_to_high_tide`):\n",
           md_table(pd.DataFrame([
               {"": "before (no fill)", "max_abs_h": round(float(old.hours_to_high_tide.abs().max()), 1),
                "NaN_tide_height": int(old.tide_height_m.isna().sum())},
               {"": "after (harmonic fill)", "max_abs_h": round(float(new.hours_to_high_tide.abs().max()), 1),
                "NaN_tide_height": int(new.tide_height_m.isna().sum())}])) + "\n",
           f"After the fix `hours_to_high_tide` is NaN on {int(new.hours_to_high_tide.isna().sum())} hour(s) "
           f"({', '.join(f'{t:%Y-%m-%d %H:%M}' for t in new.time_local[new.hours_to_high_tide.isna()])}): the fit has no high water within 7 h "
           "of them (a weak neap-tide hump), and NaN is reported instead of a far-away high. Never beyond +-7 h.\n",
           "**Hold-out validation**: fit without a 10-day window that has data, then compare the fit with the series there. "
           "Timing error = predicted minus observed high-water time (hourly data, so a resolution of 1 h).\n"]
    rows = []
    for start in ("2024-03-10", "2024-08-20", "2024-11-05", "2025-04-15", "2025-08-10", "2026-02-01"):
        v = tide.holdout_validation(series, start, 10)
        rows.append({"window": f"{start} + 10 d", "RMSE_m": round(v["rmse_m"], 3), "bias_m": round(v["bias_m"], 3),
                     "series_std_m": round(v["series_std_m"], 3), "highs_matched": f"{v['n_highs_matched']}/{v['n_highs']}",
                     "mean_abs_timing_h": round(v["timing_mean_abs_h"], 2), "max_abs_timing_h": round(v["timing_max_abs_h"], 1)})
    df = pd.DataFrame(rows)
    out += [md_table(df) + "\n",
            f"Mean over windows: RMSE {df.RMSE_m.mean():.3f} m (the series itself varies by {df.series_std_m.mean():.2f} m std), "
            f"mean absolute high-water timing error {df.mean_abs_timing_h.mean():.2f} h.\n",
            "The fit reproduces the astronomical tide; it cannot reproduce weather surge, so filled hours carry an error of about "
            "the RMSE above. This matters only for the " + f"{int(mask.sum())} filled hours ({mask.mean():.1%}), which are flagged in `tide_filled`.\n"]
    return out


def main() -> None:
    readings = load_archive()
    stations = pd.read_parquet(ROOT / "data" / "interim" / "stations.parquet")
    names = dict(zip(stations.graph_id.astype(str), stations.name))
    clean, flags = qc.clean_readings(readings)
    progress = json.loads((HIST / "_progress.json").read_text()) if (HIST / "_progress.json").exists() else {}
    n_rf, n_wl = readings[readings.kind == "rf"].graph_id.nunique(), readings[readings.kind == "wl"].graph_id.nunique()

    out = [f"# Data QC report\n",
           f"Generated {date.today():%d %b %Y} by `scripts/qc_report.py` on the JPS history archive as it stands today: "
           f"{n_rf} rain gauges and {n_wl} river stations, {len(readings):,} 15-min rows, "
           f"{readings.time_local.min():%Y-%m-%d} to {readings.time_local.max():%Y-%m-%d}"
           + (f" (archive progress {progress.get('done')}/{progress.get('total')} station series)" if progress else "")
           + ". **The archive is still being filled; this report will be regenerated when it finishes** "
           "(`python scripts/qc_report.py`).\n",
           "Rules live in `floodready/qc.py` and run inside `engine/replay.py::load_archive_readings` and `live.py::load_live_readings`, "
           "so replay, training, the API and live data all see the cleaned values. A flagged value becomes NaN, never 0.\n",
           "**Live mode:** `wl_spike` and `rain_after_gap` need the next reading. A gauge's latest reading is kept and judged when the next "
           "one arrives, so a real rise or storm after an outage is never hidden. Archive cleaning (replay, training) sees the reading at "
           "t+15 min, live cleaning does not: a small train/serve difference, limited to the latest reading of each gauge.\n",
           "## 1. Summary\n"]
    summary = flags.groupby("rule").agg(readings=("value", "size"), stations=("graph_id", "nunique")).reindex(list(RULE_TEXT)).fillna(0).astype(int)
    summary = summary.reset_index().assign(rule_text=lambda d: d.rule.map(RULE_TEXT))
    out.append(md_table(summary) + "\n")
    rain_valid = int(readings[readings.kind == "rf"].rain_15min_mm.notna().sum())
    out.append(f"{int(flags.rule.str.startswith('rain').sum())} of {rain_valid:,} rain readings "
               f"({flags.rule.str.startswith('rain').sum() / rain_valid:.4%}) and {int((flags.rule == 'wl_spike').sum())} river readings removed.\n")
    kept_max = float(clean.rain_15min_mm.max())
    imp = flags[flags.rule == "rain_implausible"]
    out.append(f"Thresholds: the largest rain value kept is {kept_max:g} mm per 15 min; the values removed by `rain_implausible` range "
               f"from {imp.value.min():g} to {imp.value.max():g} mm. `rain_after_gap` needs the continuation test (section 3): without it "
               "it removed readings of storms that began during a gap.\n")
    out.append("## 2. Flagged readings by rule and station\n")
    out += rule_sections(flags, names)
    out += false_positive_checks(readings, clean, flags)
    comp = completeness(clean, names)
    out.append("## 4. Completeness and gaps per station (after QC)\n")
    out.append("`valid_%` = non-missing readings between the station's first and last valid reading, out of the 15-min slots in that span. "
               "`longest_gap_h` = longest stretch between two valid readings.\n")
    out.append("### River level (WL)\n")
    out.append(md_table(comp[comp.kind == "wl"].drop(columns="kind")) + "\n")
    out.append("### Rain (RF)\n")
    out.append(md_table(comp[comp.kind == "rf"].drop(columns="kind")) + "\n")
    out += tide_section()
    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(flags)} flags", flags.rule.value_counts().to_dict())


if __name__ == "__main__":
    main()
