"""Backfill past alerts into the database (build plan E7): the replay engine, month by month.

Honest ML: each month is scored by the fold model that never trained on its quarter, and every step asserts
it. The ML probability is display-only (`ml_drives_alerts: false`). Only alerts are written (flagged
`is_backfill`, ids end `~backfill`); street states are not. A month's previous rows are replaced first, so a
re-run is idempotent. Each month is committed on its own (a crash keeps the finished months). The engine starts `WARMUP` before the
month so alerts already open at the 1st are not re-issued; only alerts issued from the month start are kept.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

import geopandas as gpd
import pandas as pd
import yaml

from ..db import repo
from . import replay, street_stations

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
WARMUP = timedelta(days=1)   # engine state is rebuilt from this long before each month


def _cfg(name: str) -> dict:
    return yaml.safe_load((ROOT / "config" / name).read_text(encoding="utf-8"))


def _months(start: datetime, end: datetime, step: timedelta) -> list[tuple[datetime, datetime]]:
    """[(first step, last step)] per calendar month; steps on the `step` grid from `start`, last step <= end."""
    out, cur = [], start
    while cur <= end:
        nxt = datetime(cur.year + (cur.month == 12), cur.month % 12 + 1, 1)
        last = min(end, nxt - step)
        out.append((cur, last))
        cur = nxt
    return out


def _excluded_fold(models_dir: Path, fold: int) -> int | None:
    meta = Path(models_dir) / f"trigger_v1_oof{fold}.json"
    return json.loads(meta.read_text(encoding="utf-8")).get("excluded_fold")


def oof_bundle(models_dir: Path, when: datetime) -> tuple[dict, int]:
    """(model bundle, fold) for the quarter containing `when`: the model trained WITHOUT that quarter.
    Raises if only the final (in-sample) model exists or the model's recorded excluded fold differs."""
    from ..ml import dataset, predict
    fold = int(dataset.fold_of([when])[0])
    bundle = predict.bundle_for(Path(models_dir), when, live=False)
    if bundle is None or not bundle.get("out_of_sample"):
        raise RuntimeError(f"no out-of-fold model for {when:%Y-%m} (fold {fold}); refusing to backfill with an in-sample model")
    recorded = _excluded_fold(models_dir, fold)
    if recorded != fold:
        raise RuntimeError(f"model file for fold {fold} records excluded fold {recorded}")
    return bundle, fold


def monthly_counts(conn, township_id: str) -> dict[str, dict[str, int]]:
    """{month: {level: n}} of the township's backfill alerts (kind 'alert' only; all-clears are not counted)."""
    from sqlalchemy import select
    from ..db import schema
    a = schema.alerts
    out: dict[str, dict[str, int]] = {}
    rows = conn.execute(select(a.c.issued_at, a.c.level).where(a.c.is_backfill.is_(True), a.c.township_id == township_id,
                                                              a.c.kind == "alert"))
    for issued_at, level in rows:
        month = out.setdefault(f"{issued_at:%Y-%m}", {})
        month[level] = month.get(level, 0) + 1
    return dict(sorted(out.items()))


def run_backfill(start: datetime, end: datetime, township_id: str, engine, step: timedelta = timedelta(minutes=15), *,
                 data_dir: Path | None = None, models_dir: Path | None = None, readings: pd.DataFrame | None = None,
                 stations: pd.DataFrame | None = None, tide: pd.DataFrame | None = None,
                 mapping: dict | None = None) -> dict[str, int]:
    """Replay [start, end] for the township month by month and store the alerts. Returns rows inserted per month.

    `data_dir` holds raw/jps_hist and interim/ (read only). `readings`/`stations`/`tide`/`mapping` override the
    data loading (tests). `engine` is a SQLAlchemy engine; each month is written in its own transaction."""
    town = next(t for t in _cfg("townships.yaml")["townships"] if t["id"] == township_id)
    station_ids = [s["graph_id"] for s in town["stations"]]
    wl_ids = [s["graph_id"] for s in town["stations"] if "WL" in s.get("types", [])]
    rules_cfg, ml_cfg, matrix = _cfg("rules.yaml"), _cfg("ml.yaml"), _cfg("risk_matrix.yaml")["matrix"]
    geo = ROOT / "assets" / "geo"
    streets = gpd.read_file(geo / f"{township_id.lower()}_streets.geojson")[["street_id", "susceptibility"]]
    if mapping is None:
        mapping = street_stations.load(geo / f"{township_id.lower()}_street_stations.json")
    models_dir = Path(models_dir or ROOT / "models")
    hist = ids = None
    if readings is None:
        from ..ml import dataset
        data_dir = Path(data_dir or ROOT / "data")
        stations = pd.read_parquet(data_dir / "interim" / "stations.parquet")
        hist = data_dir / "raw" / "jps_hist"
        archived = {p.stem for p in (hist / "rf").glob("*.parquet")} | {p.stem for p in (hist / "wl").glob("*.parquet")}
        ids = dataset.township_station_ids(town, stations, archived)
        tide_path = data_dir / "interim" / "tide_hourly.parquet"
        tide = pd.read_parquet(tide_path) if tide_path.exists() and tide is None else tide

    from ..ml import dataset
    inserted: dict[str, int] = {}
    for first, last in _months(start, end, step):
        t0 = time.perf_counter()
        bundle, fold = oof_bundle(models_dir, first)
        month_readings = readings if readings is not None else replay.load_archive_readings(
            hist, ids, first - WARMUP - timedelta(days=5), last, stations=stations)   # QC sees each gauge's whole archive
        rows = []
        for s in replay.run(first - WARMUP, last, step, month_readings, stations, streets, station_ids, rules_cfg, matrix,
                            ml_bundle=bundle, ml_cfg=ml_cfg, wl_ids=wl_ids, tide=tide, street_stations=mapping):
            if s.time < first:
                continue   # warm-up step: builds state, nothing kept (and may lie in the previous quarter)
            step_fold = int(dataset.fold_of([s.time])[0])
            if step_fold != fold:
                raise RuntimeError(f"{s.time}: fold {step_fold} scored by the model that excluded fold {fold}")
            rows.extend(a for a in s.alerts if a.issued_at >= first)
        with engine.begin() as conn:
            repo.replace_backfill(conn, township_id, first, last + step)
            repo.insert_alerts(conn, rows, is_replay=False, is_backfill=True)
        key = f"{first:%Y-%m}"
        inserted[key] = inserted.get(key, 0) + len(rows)
        log.info("backfill %s %s: %d alert rows in %.0f s", township_id, key, len(rows), time.perf_counter() - t0)
    return inserted
