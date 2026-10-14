"""ML2 + ML3: train the ML trigger, evaluate it against the rule floor out-of-sample, apply the gate.

Writes models/trigger_v1.joblib (+ .json card), config/ml.yaml (thresholds, gate result) and
docs/evaluation-report.md (ML section). Run after the JPS archive, build_station_lookup and build_tide.

Usage: python scripts/train_trigger.py
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from floodready.engine.replay import load_archive_readings  # noqa: E402
from floodready.ml import dataset, evaluate, train  # noqa: E402

HIST = ROOT / "data" / "raw" / "jps_hist"
THRESHOLDS = [round(x, 2) for x in np.arange(0.10, 0.96, 0.05)]


def load_yaml(name):
    return yaml.safe_load((ROOT / "config" / name).read_text(encoding="utf-8"))


def fmt(m: dict) -> str:
    lead = f"{m['median_lead_min']:.0f} min" if m["median_lead_min"] is not None else "–"
    return f"{m['detected']} / {m['crossings']} | {lead} | {m['false_per_station_month']:.2f}"


def main() -> None:
    rules_cfg, ml_cfg = load_yaml("rules.yaml"), load_yaml("ml.yaml")
    stations = pd.read_parquet(ROOT / "data" / "interim" / "stations.parquet")
    wl_ok = stations[(stations.kind == "wl") & stations.thresholds_ok & stations.lat.notna()]
    wl_ids = sorted(set(p.stem for p in (HIST / "wl").glob("*.parquet")) & set(wl_ok.graph_id))
    rf_archived = set(p.stem for p in (HIST / "rf").glob("*.parquet"))
    near = set(dataset.rain_stations_near(stations, wl_ids, km=25, available=rf_archived))
    print(f"river stations: {len(wl_ids)} | rain stations within 25 km: {len(near)}")

    readings = load_archive_readings(HIST, sorted(set(wl_ids) | near), datetime(2024, 1, 1), datetime.now())
    tide = pd.read_parquet(ROOT / "data" / "interim" / "tide_hourly.parquet")
    table = dataset.add_labels(dataset.build_features(readings, stations, tide, wl_ids))
    rows = dataset.training_rows(table)
    feats = dataset.FEATURES
    print(f"training rows: {len(rows):,}, positives (cross_2h): {int(rows.cross_2h.sum()):,}")

    fold_models: dict = {}
    oof = train.cross_val_proba(rows, feats, "cross_2h", models_out=fold_models)
    probs = train.smooth(rows[["graph_id", "time_local"]].assign(p=oof), minutes=ml_cfg["smoothing_min"])

    watch, warning = rules_cfg["rain"]["watch"], rules_cfg["rain"]["warning"]
    signals: dict[str, list[dict]] = {}
    for gid in wl_ids:
        g = table[table.graph_id == gid].set_index("time_local").sort_index()
        level, warn_m = g.wl_m, float(g.wl_warning_m.iloc[0])
        alert_m = float(stations[(stations.graph_id == gid) & (stations.kind == "wl")].wl_alert_m.iloc[0])
        rain_watch = (g.rain_1h_max_10km >= watch["rain_1h_min_mm"]) | (g.rain_2to4h_max_10km >= watch["rain_2to4h_min_mm"])
        rain_warn = (g.rain_1h_max_10km > warning["rain_1h_above_mm"]) | (g.rain_2to4h_max_10km >= warning["rain_2to4h_min_mm"])
        river_alert = level >= alert_m
        p = probs[probs.graph_id == gid].set_index("time_local").p_smooth.reindex(g.index).fillna(0.0)
        candidates = {"rules_rain_watch": rain_watch, "rules_rain_warning": rain_warn,
                      "rules_floor_watch": rain_watch | river_alert}
        for thr in THRESHOLDS:
            candidates[f"ml_{thr}"] = p >= thr
            candidates[f"ml_or_floor_{thr}"] = (p >= thr) | rain_watch | river_alert
        for name, fired in candidates.items():
            signals.setdefault(name, []).append(evaluate.event_metrics(level, fired.fillna(False), warn_m))
    pooled = {name: evaluate.pooled(ms) for name, ms in signals.items()}
    names = dict(zip(stations[stations.kind == "wl"].graph_id, stations[stations.kind == "wl"].name))

    floor, rain_only = pooled["rules_floor_watch"], pooled["rules_rain_watch"]
    p_watch, passed, criterion = evaluate.pick_threshold([(t, pooled[f"ml_{t}"]) for t in THRESHOLDS], floor, ml_cfg["gate"])
    p_warning, _, _ = evaluate.pick_threshold([(t, pooled[f"ml_{t}"]) for t in THRESHOLDS if t > p_watch] or [(p_watch, pooled[f"ml_{p_watch}"])],
                                              pooled["rules_rain_warning"], ml_cfg["gate"])
    p_warning = max(p_warning, round(p_watch + 0.1, 2))
    ml_m, combo = pooled[f"ml_{p_watch}"], pooled[f"ml_or_floor_{p_watch}"]

    print("\nOut-of-sample, will the river cross its warning level? (detected / crossings | median lead | false alarms per station-month)")
    for label, m in [("Rules: rain only (Watch)", rain_only), ("Rules: rain + river alert (floor)", floor),
                     ("Rules: rain Warning", pooled["rules_rain_warning"]), (f"ML p >= {p_watch}", ml_m),
                     (f"Shipped: max(ML p >= {p_watch}, floor)", combo)]:
        print(f"  {label:42s} {fmt(m)}")
    print(f"gate vs floor: {'PASS (' + criterion + ')' if passed else 'FAIL'}; p_watch={p_watch}, p_warning={p_warning}")

    model = train.fit_final(rows, feats, "cross_2h")
    card = {"data_from": str(rows.time_local.min()), "data_to": str(rows.time_local.max()), "river_stations": wl_ids,
            "rain_stations": len(near), "rows": len(rows), "positives": int(rows.cross_2h.sum()),
            "validation": "4 time-blocked folds (calendar quarters, round-robin); out-of-fold probabilities",
            "p_watch": p_watch, "p_warning": p_warning, "gate_passed": passed, "gate_criterion": criterion,
            "metrics": {"rules_floor_watch": floor, "rules_rain_watch": rain_only, "ml": ml_m, "shipped": combo}}
    train.save_model(model, ROOT / "models" / "trigger_v1.joblib", feats, card)
    for fold, fold_model in fold_models.items():  # for out-of-sample replays of past events
        train.save_model(fold_model, ROOT / "models" / f"trigger_v1_oof{fold}.joblib", feats,
                         {"excluded_fold": fold, "note": "trained without this fold; used to replay past events in it"})

    ml_yaml = (ROOT / "config" / "ml.yaml").read_text(encoding="utf-8")
    ml_yaml = _set(ml_yaml, "p_watch", p_watch)
    ml_yaml = _set(ml_yaml, "p_warning", p_warning)
    ml_yaml = _set(ml_yaml, "ml_drives_alerts", "true" if passed else "false")
    (ROOT / "config" / "ml.yaml").write_text(ml_yaml, encoding="utf-8")

    pm = probs[(probs.graph_id == "PEKANMERU") & (probs.time_local.between("2024-11-12 07:30", "2024-11-12 09:30"))]
    sample = ", ".join(f"{t:%H:%M} {v:.2f}" for t, v in zip(pm.time_local, pm.p_smooth))
    print("12 Nov 2024, Sg Binjai, out-of-fold p(cross within 2 h):", sample)
    per_station = [(gid, names.get(gid, gid), signals["rules_floor_watch"][i], signals[f"ml_{p_watch}"][i]) for i, gid in enumerate(wl_ids)]
    _write_report(wl_ids, len(near), rows, pooled, rain_only, floor, ml_m, combo, p_watch, p_warning, passed, criterion, sample, per_station)


def _set(text: str, key: str, value) -> str:
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.startswith(f"{key}:"):
            comment = line[line.index("#"):] if "#" in line else ""
            lines[i] = f"{key}: {value}" + (f"   {comment}" if comment else "")
    return "\n".join(lines)


def _write_report(wl_ids, n_rf, rows, pooled, rain_only, floor, ml_m, combo, p_watch, p_warning, passed, criterion, sample, per_station):
    def row(label, m):
        lead = f"{m['median_lead_min']:.0f} min" if m["median_lead_min"] is not None else "–"
        return f"| {label} | {m['detected']} / {m['crossings']} | {lead} | {m['false_per_station_month']:.2f} |"

    verdict = (f"**PASS ({criterion})**: ML drives alert levels (`ml_drives_alerts: true`)." if passed else
               "**FAIL**: ML does not yet beat the rule floor, so it is shown as a probability while the rules decide alert levels (`ml_drives_alerts: false`).")
    text = f"""# Evaluation report

Generated by `scripts/train_trigger.py` on {datetime.now():%Y-%m-%d %H:%M}. All ML numbers are **out-of-fold**: every period is scored by a model that never trained on it.

## ML trigger vs the JPS rule floor

**Question:** will the river cross its own warning level within the next 2 h? Each river station's own JPS thresholds give the labels; no news labels are needed.

- **Data:** {len(wl_ids)} river stations ({', '.join(wl_ids)}) and {n_rf} rain stations within 25 km, {rows.time_local.min():%b %Y} → {rows.time_local.max():%b %Y}, {len(rows):,} quarter hours below warning level.
- **Validation:** 4 time-blocked folds (calendar quarters, round-robin).
- **Scoring:** a crossing is detected if the signal fired 3 h to 15 min before it; a false alarm is an alarm with no crossing in the next 3 h.

| Signal | Detected / crossings | Median lead | False alarms per station-month |
| --- | --- | --- | --- |
{row("Rules: rain only (Watch)", rain_only)}
{row("Rules: rain + river at alert level (the floor)", floor)}
{row("Rules: rain Warning", pooled["rules_rain_warning"])}
{row(f"ML trigger, p ≥ {p_watch}", ml_m)}
{row(f"Shipped: higher of ML (p ≥ {p_watch}) and the floor", combo)}

**Gate** (ML vs the floor, from `docs/ml-feasibility.md`): {verdict}

Thresholds chosen on out-of-fold predictions: `p_watch = {p_watch}`, `p_warning = {p_warning}`.

**12 Nov 2024 (Sg. Binjai di Pekan Meru, crossed 4.0 m at 09:30), out-of-fold probability of crossing within 2 h:** {sample}

{_station_section(per_station)}
**Limits:**
- These are only the stations archived so far; retrain when the archive is complete.
- Thresholds were picked on the same out-of-fold predictions they are reported on, which is slightly optimistic. A nested selection would be stricter.
- The tide comes from a global model (Open-Meteo Marine), not JUPEM tables.
"""
    (ROOT / "docs" / "evaluation-report.md").write_text(text, encoding="utf-8")


def _station_section(per_station) -> str:
    def cell(m):
        lead = f"{m['median_lead_min']:.0f} min" if m["median_lead_min"] is not None else "–"
        return f"{m['detected']} / {m['crossings']}, {lead}, {m['false_per_month']:.2f}"
    lines = ["**Per river station** (detected / crossings, median lead, false alarms per month):", "",
             "| Station | Rule floor | ML trigger |", "| --- | --- | --- |"]
    for gid, name, f, m in sorted(per_station, key=lambda r: -r[2]["crossings"]):
        lines.append(f"| {name} (`{gid}`) | {cell(f)} | {cell(m)} |")
    busiest = max(per_station, key=lambda r: r[2]["crossings"])
    rest = [r for r in per_station if r[0] != busiest[0]]
    if rest:
        f_rest = evaluate.pooled([r[2] for r in rest]); m_rest = evaluate.pooled([r[3] for r in rest])
        share = busiest[2]["crossings"] / max(sum(r[2]["crossings"] for r in per_station), 1)
        lines += ["", f"{busiest[1]} holds {share:.0%} of all crossings. It is on the tidal lower Sg. Klang and crosses warning with the tides, "
                  "so pooled numbers lean on tide prediction. **Without it:** rule floor "
                  f"{f_rest['detected']} / {f_rest['crossings']} ({f_rest['median_lead_min'] or 0:.0f} min, {f_rest['false_per_station_month']:.2f}/station-month) vs ML "
                  f"{m_rest['detected']} / {m_rest['crossings']} ({m_rest['median_lead_min'] or 0:.0f} min, {m_rest['false_per_station_month']:.2f}/station-month)."]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
