"""ML2 + ML3: train the ML trigger, calibrate it, evaluate it against the rule floor out-of-sample, apply gate v2.

Writes models/trigger_v1.joblib (+ .json card) and trigger_v1_oof{k}.joblib (fold models for out-of-sample
replays), config/ml.yaml (p_watch, ml_drives_alerts, gate_version) and docs/evaluation-report.md.
Run after the JPS archive, build_station_lookup and build_tide.

Steps
  1. Calibration: three variants compared on out-of-fold Brier / ECE / PR-AUC (floodready.ml.train.cross_val_calibrated).
  2. Events: every (river station, calendar quarter) block is scored for the rule floor, ML alone and
     two_tier = floor OR calibrated ML p >= theta, for a grid of theta.
  3. Gate v2 (docs/plans/2026-10-16-IMP-ml-data-street-improvements.md section 3): theta per outer fold chosen on
     the other three folds only; scored on inland stations; criteria 1-3.

Usage: python scripts/train_trigger.py [--cache DIR]
  --cache DIR  keep the feature table and the calibrated training results there, to re-run only the evaluation.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from floodready.engine.replay import load_archive_readings  # noqa: E402
from floodready.ml import dataset, evaluate, train  # noqa: E402

HIST = ROOT / "data" / "raw" / "jps_hist"
THETAS = [0.02, 0.03, 0.05, 0.075, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]
LABEL = "cross_2h"

# The 15 river stations the EDA (docs/ml-data-eda.md) looked at. Any river station archived beyond these is "fresh":
# the gate was pre-registered before it was seen, so it must also hold there (gate v2 criterion 3).
EDA_STATIONS = {"26039", "26558", "3014080_", "3015001_", "3015083_", "3015084_", "3015089_", "3016080_",
                "3017107_", "3115080_", "3115083_", "3115084_", "DESAKEMUNING", "PANDAMARAN", "PEKANMERU"}

OPTIONS = {  # name -> (class_weight of the base model, isotonic calibration?)
    "balanced + isotonic": ("balanced", True),
    "no class weight + isotonic": (None, True),
    "no class weight, raw": (None, False),
}


def load_yaml(name):
    return yaml.safe_load((ROOT / "config" / name).read_text(encoding="utf-8"))


def fmt(m: dict) -> str:
    lead = f"{m['median_lead_min']:.0f} min" if m["median_lead_min"] is not None else "–"
    prec = f"{m['alarm_precision']:.0%}" if m.get("alarm_precision") is not None else "–"
    fa = m["false_per_station_month"]
    return f"{m['detected']} / {m['crossings']} | {lead} | {fa:.2f} | {prec}" if fa is not None else f"{m['detected']} / {m['crossings']} | {lead} | – | {prec}"


# ------------------------------------------------------------------ data and training

def build_rows(rules_cfg):
    stations = pd.read_parquet(ROOT / "data" / "interim" / "stations.parquet")
    wl_ok = stations[(stations.kind == "wl") & stations.thresholds_ok & stations.lat.notna()]
    wl_ids = sorted(set(p.stem for p in (HIST / "wl").glob("*.parquet")) & set(wl_ok.graph_id))
    rf_archived = set(p.stem for p in (HIST / "rf").glob("*.parquet"))
    near = set(dataset.rain_stations_near(stations, wl_ids, km=25, available=rf_archived))
    print(f"river stations: {len(wl_ids)} | rain stations within 25 km: {len(near)}")
    readings = load_archive_readings(HIST, sorted(set(wl_ids) | near), datetime(2024, 1, 1), datetime.now())
    tide = pd.read_parquet(ROOT / "data" / "interim" / "tide_hourly.parquet")
    table = dataset.add_labels(dataset.build_features(readings, stations, tide, wl_ids))
    return stations, wl_ids, len(near), table


def calibration_study(rows, feats):
    """Fit both class-weight variants (isotonic maps fitted out-of-sample) and score the three options."""
    runs = {}
    for cw in ("balanced", None):
        t0 = datetime.now()
        runs[cw] = train.cross_val_calibrated(rows, feats, LABEL, class_weight=cw)
        print(f"  class_weight={cw}: {(datetime.now() - t0).total_seconds() / 60:.1f} min")
    y = rows[LABEL].to_numpy()
    results = {}
    for name, (cw, iso) in OPTIONS.items():
        p = runs[cw]["oof_cal" if iso else "oof_raw"]
        results[name] = {"p": p, "brier": evaluate.brier(p, y), "ece": evaluate.ece(p, y),
                         "pr_auc": float(average_precision_score(y, p)), "roc_auc": float(roc_auc_score(y, p)),
                         "reliability": evaluate.reliability_table(p, y)}
    return runs, results


# ------------------------------------------------------------------ event blocks

def station_inputs(table, stations, gid, rules_cfg, p_smooth):
    g = table[table.graph_id == gid].set_index("time_local").sort_index()
    watch, warning = rules_cfg["rain"]["watch"], rules_cfg["rain"]["warning"]
    alert_m = float(stations[(stations.graph_id == gid) & (stations.kind == "wl")].wl_alert_m.iloc[0])
    rain_watch = (g.rain_1h_max_10km >= watch["rain_1h_min_mm"]) | (g.rain_2to4h_max_10km >= watch["rain_2to4h_min_mm"])
    rain_warn = (g.rain_1h_max_10km > warning["rain_1h_above_mm"]) | (g.rain_2to4h_max_10km >= warning["rain_2to4h_min_mm"])
    floor = (rain_watch | (g.wl_m >= alert_m)).fillna(False)
    p = p_smooth.reindex(g.index).fillna(0.0)
    return {"level": g.wl_m, "warn_m": float(g.wl_warning_m.iloc[0]), "floor": floor,
            "rain_watch": rain_watch.fillna(False), "rain_warn": rain_warn.fillna(False), "p": p}


def add_theta(block, theta):
    d = block["data"]
    block["metrics"][f"ml_{theta}"] = evaluate.event_metrics(d["level"], d["p"] >= theta, d["warn_m"])
    block["metrics"][f"two_tier_{theta}"] = evaluate.event_metrics(d["level"], (d["p"] >= theta) | d["floor"], d["warn_m"])


def make_blocks(inputs: dict, tidal: set, fresh: set) -> list[dict]:
    blocks = []
    for gid, d in inputs.items():
        quarters = d["level"].index.to_period("Q")
        for q in sorted(set(quarters)):
            sel = quarters == q
            if sel.sum() < 96:
                continue
            part = {k: (v[sel] if isinstance(v, pd.Series) else v) for k, v in d.items()}
            blk = {"station": gid, "fold": int(dataset.fold_of(pd.Series([part["level"].index[0]]))[0]),
                   "inland": gid not in tidal, "fresh": gid in fresh, "data": part,
                   "metrics": {"floor": evaluate.event_metrics(part["level"], part["floor"], part["warn_m"]),
                               "rain_watch": evaluate.event_metrics(part["level"], part["rain_watch"], part["warn_m"]),
                               "rain_warning": evaluate.event_metrics(part["level"], part["rain_warn"], part["warn_m"])}}
            for th in THETAS:
                add_theta(blk, th)
            blocks.append(blk)
    return blocks


def pool(blocks, key):
    return evaluate.pooled([b["metrics"][key] for b in blocks])


# ------------------------------------------------------------------ main

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", type=Path, default=None)
    args = ap.parse_args()
    rules_cfg, ml_cfg = load_yaml("rules.yaml"), load_yaml("ml.yaml")
    gate_cfg = ml_cfg["gate"]
    feats = dataset.FEATURES

    cache = args.cache / "train_cache.joblib" if args.cache else None
    if cache and cache.exists():
        print(f"loading cache {cache}")
        stations, wl_ids, n_rf, table, runs, results = joblib.load(cache)
        rows = dataset.training_rows(table)
    else:
        stations, wl_ids, n_rf, table = build_rows(rules_cfg)
        rows = dataset.training_rows(table)
        print(f"training rows: {len(rows):,}, positives ({LABEL}): {int(rows[LABEL].sum()):,}")
        runs, results = calibration_study(rows, feats)
        if cache:
            args.cache.mkdir(parents=True, exist_ok=True)
            joblib.dump((stations, wl_ids, n_rf, table, runs, results), cache)

    # 1. calibration choice
    chosen = train.pick_calibration({k: {"brier": v["brier"], "pr_auc": v["pr_auc"]} for k, v in results.items()})
    cw, use_iso = OPTIONS[chosen]
    print("\ncalibration (out-of-fold):")
    for name, r in results.items():
        print(f"  {name:28s} Brier {r['brier']:.5f}  ECE {r['ece']:.4f}  PR-AUC {r['pr_auc']:.4f}  ROC-AUC {r['roc_auc']:.4f}{'  <- chosen' if name == chosen else ''}")
    run = runs[cw]
    oof = results[chosen]["p"]
    final = run["final_model"] if use_iso else run["final_model"].without_calibration()
    fold_models = {k: (m if use_iso else m.without_calibration()) for k, m in run["fold_models"].items()}

    # 2. tidal vs inland, fresh stations
    levels = {gid: g.set_index("time_local").wl_m for gid, g in table.groupby("graph_id")}
    tidal = evaluate.tidal_stations(levels)
    fresh = set(wl_ids) - EDA_STATIONS
    print(f"tidal (lag-25 autocorrelation < -0.2): {sorted(tidal)} | fresh: {sorted(fresh)}")

    # 3. event blocks and gate v2
    probs = train.smooth(rows[["graph_id", "time_local"]].assign(p=oof), minutes=ml_cfg["smoothing_min"])
    inputs = {gid: station_inputs(table, stations, gid, rules_cfg, probs[probs.graph_id == gid].set_index("time_local").p_smooth)
              for gid in wl_ids}
    blocks = make_blocks(inputs, tidal, fresh)
    inland = [b for b in blocks if b["inland"]]

    max_ratio = gate_cfg["max_false_alarm_ratio"]
    theta_by_fold = evaluate.nested_thetas(blocks, THETAS, max_ratio)
    p_watch = round(float(np.median(list(theta_by_fold.values()))), 4)
    for b in blocks:
        if f"two_tier_{p_watch}" not in b["metrics"]:
            add_theta(b, p_watch)
    print(f"theta per outer fold (chosen on the other folds): {theta_by_fold}; shipped p_watch = median = {p_watch}")

    def group(bs):
        return {"floor": pool(bs, "floor"), "rain_watch": pool(bs, "rain_watch"), "rain_warning": pool(bs, "rain_warning"),
                "ml": pool(bs, f"ml_{p_watch}"), "two_tier": pool(bs, f"two_tier_{p_watch}"),
                "ml_nested": evaluate.nested_pool(bs, theta_by_fold, "ml"),
                "two_tier_nested": evaluate.nested_pool(bs, theta_by_fold, "two_tier")} if bs else None

    groups = {"inland": group(inland), "tidal": group([b for b in blocks if not b["inland"]]), "pooled": group(blocks)}
    fresh_blocks = [b for b in inland if b["fresh"]]
    groups["fresh"] = group(fresh_blocks)
    old_blocks = [b for b in inland if not b["fresh"]]
    groups["inland_eda"] = group(old_blocks)
    fresh_g = groups["fresh"]
    verdict = evaluate.gate_v2(groups["inland"]["floor"], groups["inland"]["two_tier_nested"],
                               fresh_g["floor"] if fresh_g else None, fresh_g["two_tier_nested"] if fresh_g else None, gate_cfg)
    passed = verdict["passed"]
    for name in ("inland", "tidal", "pooled"):
        g = groups[name]
        if g:
            print(f"\n[{name}] detected / crossings | median lead | false alarms per station-month | alarm precision")
            for label, key in [("rules rain Watch", "rain_watch"), ("floor (rain Watch or river alert)", "floor"),
                               (f"ML alone p>={p_watch}", "ml"), (f"two_tier p>={p_watch}", "two_tier"),
                               ("two_tier, nested theta", "two_tier_nested")]:
                print(f"  {label:36s} {fmt(g[key])}")
    print(f"\ngate v2: {'PASS' if passed else 'FAIL'}  main={verdict['main']}  fresh_gating={verdict['fresh_gating']} fresh={verdict['fresh']}")

    # 4. save models and config
    card = {"data_from": str(rows.time_local.min()), "data_to": str(rows.time_local.max()), "river_stations": wl_ids,
            "rain_stations": n_rf, "rows": len(rows), "positives": int(rows[LABEL].sum()),
            "validation": "4 time-blocked folds (calendar quarters, round-robin); out-of-fold probabilities",
            "calibration": chosen, "calibration_scores": {k: {m: v[m] for m in ("brier", "ece", "pr_auc", "roc_auc")} for k, v in results.items()},
            "p_watch": p_watch, "theta_by_fold": theta_by_fold, "gate_version": 2, "gate_passed": passed,
            "tidal_stations": sorted(tidal), "fresh_stations": sorted(fresh)}
    train.save_model(final, ROOT / "models" / "trigger_v1.joblib", feats, card, params=run["params"])
    for fold, fold_model in fold_models.items():  # for out-of-sample replays of past events
        train.save_model(fold_model, ROOT / "models" / f"trigger_v1_oof{fold}.joblib", feats,
                         {"excluded_fold": fold, "calibration": chosen,
                          "note": "trained and calibrated without this fold; used to replay past events in it"}, params=run["params"])

    ml_yaml = (ROOT / "config" / "ml.yaml").read_text(encoding="utf-8")
    for key, value in (("p_watch", p_watch), ("ml_drives_alerts", "true" if passed else "false"), ("gate_version", 2),
                       ("calibration", f'"{chosen}"')):
        ml_yaml = _set(ml_yaml, key, value)
    (ROOT / "config" / "ml.yaml").write_text(ml_yaml, encoding="utf-8")

    pm = probs[(probs.graph_id == "PEKANMERU") & (probs.time_local.between("2024-11-12 07:30", "2024-11-12 09:30"))]
    sample = ", ".join(f"{t:%H:%M} {v:.2f}" for t, v in zip(pm.time_local, pm.p_smooth))
    print("12 Nov 2024, Sg Binjai, out-of-fold p(cross within 2 h):", sample)
    names = dict(zip(stations[stations.kind == "wl"].graph_id, stations[stations.kind == "wl"].name))
    _write_report(dict(wl_ids=wl_ids, n_rf=n_rf, rows=rows, results=results, chosen=chosen, groups=groups, verdict=verdict,
                       theta_by_fold=theta_by_fold, p_watch=p_watch, tidal=tidal, fresh=fresh, blocks=blocks, names=names,
                       sample=sample, gate_cfg=gate_cfg))


def _set(text: str, key: str, value) -> str:
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.startswith(f"{key}:"):
            comment = line[line.index("#"):] if "#" in line else ""
            lines[i] = f"{key}: {value}" + (f"   {comment}" if comment else "")
            return "\n".join(lines)
    return text.rstrip("\n") + f"\n{key}: {value}\n"


# ------------------------------------------------------------------ report

def _row(label, m):
    lead = f"{m['median_lead_min']:.0f} min" if m["median_lead_min"] is not None else "–"
    prec = f"{m['alarm_precision']:.0%}" if m.get("alarm_precision") is not None else "–"
    fa = f"{m['false_per_station_month']:.2f}" if m["false_per_station_month"] is not None else "–"
    return f"| {label} | {m['detected']} / {m['crossings']} | {lead} | {fa} | {prec} |"


def _group_table(title, g, p_watch):
    if not g:
        return f"### {title}\n\nNo stations in this group.\n"
    head = ["| Signal | Detected / crossings | Median lead | False alarms per station-month | Alarm precision |", "| --- | --- | --- | --- | --- |"]
    rows = [_row("Rules: rain Watch only", g["rain_watch"]), _row("Rules: rain Warning", g["rain_warning"]),
            _row("**Floor**: rain Watch or river at alert", g["floor"]),
            _row(f"ML alone, p ≥ {p_watch}", g["ml"]), _row(f"**Two-tier**: floor OR ML p ≥ {p_watch}", g["two_tier"]),
            _row("ML alone, θ chosen per fold (nested)", g["ml_nested"]), _row("Two-tier, θ chosen per fold (nested)", g["two_tier_nested"])]
    return f"### {title}\n\n" + "\n".join(head + rows) + "\n"


def _write_report(c: dict) -> None:
    p_watch, groups, verdict, cfg = c["p_watch"], c["groups"], c["verdict"], c["gate_cfg"]
    main, fresh = verdict["main"], verdict["fresh"]

    def crit(r):
        return (f"lead {r['lead_two_tier_min'] if r['lead_two_tier_min'] is not None else float('nan'):.0f} vs floor {r['lead_floor_min']:.0f} min "
                f"(needs +{cfg['min_extra_lead_min']}): {'ok' if r['lead_ok'] else 'FAIL'}; "
                f"false alarms {r['false_two_tier']:.2f} vs floor {r['false_floor']:.2f} per station-month "
                f"(needs ≤ {cfg['max_false_alarm_ratio']}×): {'ok' if r['false_alarms_ok'] else 'FAIL'}")

    cal_rows = ["| Option | Brier | ECE | PR-AUC | ROC-AUC |", "| --- | --- | --- | --- | --- |"]
    for name, r in c["results"].items():
        mark = " **(chosen)**" if name == c["chosen"] else ""
        cal_rows.append(f"| {name}{mark} | {r['brier']:.5f} | {r['ece']:.4f} | {r['pr_auc']:.4f} | {r['roc_auc']:.4f} |")
    bins = c["results"][next(iter(c["results"]))]["reliability"]["bin"].tolist()
    rel = ["| Option | " + " | ".join(bins) + " |", "| --- |" + " --- |" * len(bins)]
    for name, r in c["results"].items():
        t = r["reliability"]
        rel.append(f"| {name} | " + " | ".join("–" if n == 0 else f"{o:.1%} (n={n:,})" for n, o in zip(t.n, t.observed)) + " |")

    if verdict["passed"]:
        status = ("**PASS**: ML may raise a street to **Watch** (`ml_drives_alerts: true`, `ml_max_level: watch`). "
                  "Warning and Danger still come only from the JPS rules.")
    else:
        status = "**FAIL**: ML stays informational (`ml_drives_alerts: false`). Warning and Danger come only from the JPS rules."
    fresh_line = "No fresh stations in the archive yet."
    if fresh:
        fr = groups["fresh"]
        fresh_line = (f"{len(c['fresh'])} fresh stations, {fr['floor']['crossings']} inland crossings. "
                      f"{'**Gating** (≥ ' + str(cfg['min_fresh_crossings']) + ' crossings)' if verdict['fresh_gating'] else 'Reported, not gating (< ' + str(cfg['min_fresh_crossings']) + ' crossings)'}: {crit(fresh)}.")
    folds = ", ".join(f"fold {k}: {v}" for k, v in c["theta_by_fold"].items())

    text = f"""# Evaluation report

Generated by `scripts/train_trigger.py` on {datetime.now():%Y-%m-%d %H:%M}. All ML numbers are **out-of-fold**: every period is scored by a model that never trained on it, and the calibration map and the threshold θ for a fold never saw that fold either.

**Question:** will the river cross its own warning level within the next 2 h? Each river station's own JPS thresholds give the labels.

- **Data:** {len(c['wl_ids'])} river stations and {c['n_rf']} rain stations within 25 km, {c['rows'].time_local.min():%b %Y} → {c['rows'].time_local.max():%b %Y}, {len(c['rows']):,} quarter hours below warning level.
- **Validation:** 4 time-blocked folds (calendar quarters, round-robin). Events are scored per (station, quarter).
- **Scoring:** a crossing is detected if the signal fired 3 h to 15 min before it; a false alarm is an alarm with no crossing in the next 3 h; alarm precision is the share of alarms followed by a crossing.
- **Inland vs tidal** is data-driven: a station is tidal if the lag-25 (6.25 h) autocorrelation of its level is below −0.2. Tidal: {', '.join(f'`{g}`' for g in sorted(c['tidal'])) or 'none'}.

## Gate v2 (pre-registered 16 Oct 2026)

{status}

Signals: **floor** = rule Watch (rain) or river at alert; **two-tier** = floor OR calibrated ML probability ≥ θ. Scored on **inland** stations. θ per outer fold is chosen on the other three folds only (the θ with the most detections whose false alarms stay within {cfg['max_false_alarm_ratio']}× the floor's); the shipped `p_watch` is the median.

- θ per fold: {folds}. **Shipped `p_watch = {p_watch}`.**
- Criterion 1 (median lead ≥ floor + {cfg['min_extra_lead_min']} min) and 2 (false alarms ≤ {cfg['max_false_alarm_ratio']}× floor), inland, nested θ: {crit(main)}.
- Criterion 3 (fresh stations, never seen by the EDA): {fresh_line}

## Calibration

The ML trigger is trained with `class_weight="balanced"` in the old pipeline, which made its probabilities far too high (EDA §6: predicted 0.5–0.7 → 4.6% observed). Three options are compared on out-of-fold predictions; each calibration map is fitted on inner out-of-fold predictions of the outer training set only, then the base model is refitted on the whole outer training set. Pick: lowest Brier among options with PR-AUC within 0.01 of the best.

{chr(10).join(cal_rows)}

Observed crossing rate by predicted-probability bin (a calibrated model matches the bin range):

{chr(10).join(rel)}

## Results

{_group_table("Inland stations (headline)", groups["inland"], p_watch)}
{_group_table("Tidal stations", groups["tidal"], p_watch)}
{_group_table("All stations pooled", groups["pooled"], p_watch)}
Rows without "nested" use the shipped θ, which was the median of fold choices that saw the other folds' data, so they are slightly optimistic; the gate uses the nested rows.

**12 Nov 2024 (Sg. Binjai di Pekan Meru, crossed 4.0 m at 09:30), out-of-fold calibrated probability of crossing within 2 h:** {c['sample']}

{_station_section(c)}
**Limits:**
- Thresholds, calibration and the gate were fitted on the same archive that is scored, but never on the fold being scored.
- Events are scored per quarter block, so an alarm and a crossing on opposite sides of a quarter boundary are not matched.
- The tide comes from a global model (Open-Meteo Marine), not JUPEM tables.
"""
    (ROOT / "docs" / "evaluation-report.md").write_text(text, encoding="utf-8")


def _station_section(c) -> str:
    p = c["p_watch"]
    by = {}
    for b in c["blocks"]:
        by.setdefault(b["station"], []).append(b)

    def cell(m):
        lead = f"{m['median_lead_min']:.0f} min" if m["median_lead_min"] is not None else "–"
        fa = f"{m['false_per_station_month']:.2f}" if m["false_per_station_month"] is not None else "–"
        return f"{m['detected']} / {m['crossings']}, {lead}, {fa}"

    lines = ["## Per river station", "", "Detected / crossings, median lead, false alarms per month.", "",
             "| Station | Type | Rule floor | ML alone | Two-tier |", "| --- | --- | --- | --- | --- |"]
    rowsx = []
    for gid, bs in by.items():
        f, m, t = pool(bs, "floor"), pool(bs, f"ml_{p}"), pool(bs, f"two_tier_{p}")
        kind = "tidal" if gid in c["tidal"] else "inland" + (" (fresh)" if gid in c["fresh"] else "")
        rowsx.append((f["crossings"], f"| {c['names'].get(gid, gid)} (`{gid}`) | {kind} | {cell(f)} | {cell(m)} | {cell(t)} |"))
    lines += [r for _, r in sorted(rowsx, key=lambda x: -x[0])]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
