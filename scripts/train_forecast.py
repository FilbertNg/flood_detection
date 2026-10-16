"""Train the river-level forecast (improvement #12) and write docs/forecast-report.md.

Writes models/forecast_v1.joblib (final) and models/forecast_v1_oof{k}.joblib (fold models for
out-of-sample replays). All reported errors are out-of-fold: each period is predicted by a model
that never trained on it. Baseline = persistence (the level stays what it is now).

Usage: python scripts/train_forecast.py
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from floodready.engine.replay import load_archive_readings  # noqa: E402
from floodready.ml import dataset, forecast  # noqa: E402

HIST = ROOT / "data" / "raw" / "jps_hist"
RISE_M = 0.3


def build_rows():
    stations = pd.read_parquet(ROOT / "data" / "interim" / "stations.parquet")
    wl_ok = stations[(stations.kind == "wl") & stations.thresholds_ok & stations.lat.notna()]
    wl_ids = sorted(set(p.stem for p in (HIST / "wl").glob("*.parquet")) & set(wl_ok.graph_id))
    rf_archived = set(p.stem for p in (HIST / "rf").glob("*.parquet"))
    near = set(dataset.rain_stations_near(stations, wl_ids, km=25, available=rf_archived))
    print(f"river stations: {len(wl_ids)} | rain stations within 25 km: {len(near)}")
    readings = load_archive_readings(HIST, sorted(set(wl_ids) | near), datetime(2024, 1, 1), datetime.now())
    tide = pd.read_parquet(ROOT / "data" / "interim" / "tide_hourly.parquet")
    table = forecast.add_targets(dataset.build_features(readings, stations, tide, wl_ids))
    alert = stations[stations.kind == "wl"].drop_duplicates("graph_id").set_index("graph_id").wl_alert_m
    table["wl_alert_m"] = table.graph_id.map(alert)
    table["rise_obs_60m"] = table.groupby("graph_id").wl_m.diff(4)      # observed rise up to t (known at forecast time)
    rows = forecast.training_rows(table)
    rows["tidal"] = rows.graph_id.map(tidal_stations(table))
    return rows, wl_ids, sorted(near), tide


def tidal_stations(table: pd.DataFrame) -> dict[str, bool]:
    """Data-driven (as in docs/ml-data-eda.md): tidal if the lag-25 autocorrelation of the hourly-ish level is < -0.2."""
    out = {}
    for gid, g in table.groupby("graph_id"):
        lvl = g.sort_values("time_local").wl_m
        out[gid] = bool(lvl.autocorr(lag=25) < -0.2)
    return out


def score(rows: pd.DataFrame, oof: pd.DataFrame, mask: pd.Series | None = None) -> dict:
    out = {}
    m = mask if mask is not None else pd.Series(True, index=rows.index)
    for h in forecast.HORIZONS:
        actual = rows.loc[m, f"d{h}"]
        p10, p50, p90 = (oof.loc[m, f"{h}_p{q}"] for q in (10, 50, 90))
        out[h] = {"n": int(m.sum()), "mae_model": float((p50 - actual).abs().mean()), "mae_persist": float(actual.abs().mean()),
                  "coverage": float(((actual >= p10) & (actual <= p90)).mean()),
                  "p90_below": float((actual <= p90).mean()), "width": float((p90 - p10).mean())}
    return out


def table_md(res: dict) -> str:
    lines = ["| Subset | Horizon | Rows | MAE model (m) | MAE persistence (m) | Improvement | p10-p90 coverage | One-sided p90 coverage | Mean interval width (m) |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for subset, by_h in res.items():
        for h, r in by_h.items():
            if r["n"] == 0:
                continue
            gain = 1 - r["mae_model"] / r["mae_persist"] if r["mae_persist"] else float("nan")
            lines.append(f"| {subset} | +{h[0]} h | {r['n']:,} | {r['mae_model']:.3f} | {r['mae_persist']:.3f} | {gain:+.0%} | "
                         f"{r['coverage']:.0%} | {r['p90_below']:.0%} | {r['width']:.2f} |")
    return "\n".join(lines)


def main() -> None:
    rows, wl_ids, rain_ids, tide = build_rows()
    features = list(dataset.FEATURES)
    print(f"training rows (any level): {len(rows):,}; features: {len(features)}")

    fold_models: dict = {}
    oof = forecast.cross_val_changes(rows, features, models_out=fold_models, rain_ids=rain_ids, tide=tide)
    res = {
        "All rows": score(rows, oof),
        f"During rises (observed rise in last 1 h >= {RISE_M} m)": score(rows, oof, rows.rise_obs_60m >= RISE_M),
        "At or above alert level": score(rows, oof, rows.wl_m >= rows.wl_alert_m),
        "Inland stations": score(rows, oof, ~rows.tidal),
        "Tidal stations": score(rows, oof, rows.tidal),
    }
    print(table_md(res))
    per = ["| Station | Tidal | Rows | +1 h MAE model (m) | +1 h MAE persistence (m) | +2 h MAE model (m) | +2 h MAE persistence (m) |",
           "| --- | --- | --- | --- | --- | --- | --- |"]
    for gid in wl_ids:
        m = rows.graph_id == gid
        if not m.any():
            continue
        sc = score(rows, oof, m)
        per.append(f"| `{gid}` | {'yes' if rows.tidal[m].iloc[0] else 'no'} | {int(m.sum()):,} | {sc['1h']['mae_model']:.3f} | "
                   f"{sc['1h']['mae_persist']:.3f} | {sc['2h']['mae_model']:.3f} | {sc['2h']['mae_persist']:.3f} |")
    per_md = "\n".join(per)

    final = forecast.fit(rows, features, rain_ids, tide)
    forecast.save_bundle(final, ROOT / "models" / "forecast_v1.joblib")
    for fold, b in fold_models.items():
        forecast.save_bundle(b, ROOT / "models" / f"forecast_v1_oof{fold}.joblib")

    ev = rows[(rows.graph_id == "PEKANMERU") & rows.time_local.between("2024-11-12 07:00", "2024-11-12 10:00")]
    ev_lines = ["| Time | Level now (m) | Actual +1 h (m) | Forecast +1 h median (p10-p90) | Actual +2 h (m) | Forecast +2 h median (p10-p90) |",
                "| --- | --- | --- | --- | --- | --- |"]
    for i, r in ev.iterrows():
        f = {h: [r.wl_m + oof.loc[i, f"{h}_p{q}"] for q in (10, 50, 90)] for h in forecast.HORIZONS}
        ev_lines.append(f"| {r.time_local:%H:%M} | {r.wl_m:.2f} | {r.wl_m + r.d1h:.2f} | {f['1h'][1]:.2f} ({f['1h'][0]:.2f}-{f['1h'][2]:.2f}) | "
                        f"{r.wl_m + r.d2h:.2f} | {f['2h'][1]:.2f} ({f['2h'][0]:.2f}-{f['2h'][2]:.2f}) |")
    print("\n".join(ev_lines))
    (ROOT / "docs" / "forecast-report.md").write_text(report(res, rows, wl_ids, features, "\n".join(ev_lines), rain_ids, tide, per_md), encoding="utf-8")


def report(res, rows, wl_ids, features, event_table, rain_ids, tide, per_md) -> str:
    sig = forecast.tide_signature(tide)
    return f"""# River-level forecast report

Generated by `scripts/train_forecast.py` on {datetime.now():%Y-%m-%d %H:%M}. Every number is **out-of-fold**: each period is predicted by a model that never trained on it (4 time-blocked folds, calendar quarters round-robin, the same folds as the trigger).

## Method

- **Target:** change in river level at +1 h and +2 h; the current level is added back. One pooled `HistGradientBoostingRegressor(loss="quantile")` per horizon and quantile (0.1, 0.5, 0.9), using the station-relative features from `dataset.build_features` ({len(features)} features, listed in the model bundle). Predicted quantiles are sorted per row so they never cross.
- **Training rows:** every quarter hour with a known current level and known levels 1 h and 2 h ahead, at **any level** (not only below warning). A forecast is most needed while the river is already high, and the trigger's below-warning filter would remove exactly those cases.
- **Data:** {len(wl_ids)} river stations ({', '.join(wl_ids)}), {rows.time_local.min():%b %Y} to {rows.time_local.max():%b %Y}, {len(rows):,} rows.
- **Baseline:** persistence (the level stays what it is now). MAE = mean absolute error of the median forecast.
- **Rises** are selected by the rise observed in the last hour (known at forecast time), not by the future outcome, so the subset is not chosen with hindsight.
- **Coverage:** share of actual levels inside the p10-p90 range (target about 80%), and the one-sided share at or below p90 (build plan ML5 asks for 0.85-0.95).
- **Inputs recorded in each model bundle:** {len(rain_ids)} rain gauges (`rain_ids`) and the tide table fingerprint `{sig}`. Serving restricts rain readings to that gauge list, so the forecast does not drift when more gauges are archived.
- **Snapshot:** these numbers are a snapshot of the JPS archive on the day of the run. The archive was still growing and the tide file was rebuilt (WP1 gap filling) during earlier runs: the first run scored 0.049 / 0.083 m MAE overall (its gauge count was not recorded), a reviewer's reconstruction with 38 older gauges scored 0.051 / 0.089, a re-score of those models on 49 gauges gave 0.053 / 0.098, and the alert-level subset ranged from 0.15 to 0.37 m MAE and 60 to 84% coverage across snapshots. The lead retrains after integration (WP2 feature changes, full archive) and regenerates this report.
- **"Now" level:** a forecast is only made when the station's latest level is at most 30 min old; the response carries its time (`wl_now_time`).

## Results

{table_md(res)}

## Per station

{per_md}

## 12 Nov 2024, Sg. Binjai di Pekan Meru (out-of-sample)

The river crossed its 4.0 m warning level at 09:30. This day's quarter is scored by a model trained without it.

{event_table}

The model follows the rise but under-forecasts it: during the fast rise the actual level is outside the p10-p90 range in several rows (compare the Actual columns with the ranges). A flash rise this fast is the hard case; the forecast is a guide, and the JPS thresholds and the trigger decide alerts.

## Limits

- Stations are those archived so far; retrain when the archive is complete.
- The model sees rain only through gauges within 25 km and a global tide model, so a sudden local burst after t is not forecastable.
- Intervals are per-row quantile estimates, not conformal. Coverage on rare high-water rows varies between archive snapshots (see Snapshot above), so read the alert-level row as indicative.
- Gains are uneven: at some stations (see the per-station table) the model is no better than persistence; most of the pooled gain comes from tidal or fast-reacting stations. 
- Tidal stations are pooled with inland ones.
"""


if __name__ == "__main__":
    main()
