"""WP5: backfill = replay.run month by month into the DB, out-of-fold ML, idempotent."""
from datetime import datetime, timedelta
from pathlib import Path

import geopandas as gpd
import pytest
import yaml
from sqlalchemy import func, select

from floodready.db import repo, schema
from floodready.engine import backfill, replay, street_stations
from floodready.ml import dataset, predict

ROOT = Path(__file__).resolve().parents[2]
START, END = datetime(2024, 11, 12, 6, 0), datetime(2024, 11, 12, 14, 0)
STEP = timedelta(minutes=15)


def _cfg(name):
    return yaml.safe_load((ROOT / "config" / name).read_text(encoding="utf-8"))


@pytest.fixture
def conn():
    eng = repo.connect("sqlite://")
    with eng.begin() as c:
        yield c


@pytest.fixture(scope="module")
def mapping():
    return street_stations.load(ROOT / "assets" / "geo" / "bbr_street_stations.json")


def _run(conn, readings, stations, mapping, start=START, end=END):
    return backfill.run_backfill(start, end, "BBR", conn, STEP, models_dir=ROOT / "models",
                                 readings=readings, stations=stations, tide=None, mapping=mapping)


def _rows(conn):
    a = schema.alerts
    return conn.execute(select(a.c.alert_id, a.c.street_id, a.c.level, a.c.kind, a.c.issued_at, a.c.is_backfill, a.c.is_replay)
                        .order_by(a.c.alert_id)).all()


def test_matches_replay_run(conn, readings, stations, rules_cfg, matrix_cfg, mapping):
    _run(conn, readings, stations, mapping)
    rows = _rows(conn)
    assert rows
    assert all(r.is_backfill and not r.is_replay and r.alert_id.endswith("~backfill") for r in rows)

    town = next(t for t in _cfg("townships.yaml")["townships"] if t["id"] == "BBR")
    station_ids = [s["graph_id"] for s in town["stations"]]
    wl_ids = [s["graph_id"] for s in town["stations"] if "WL" in s.get("types", [])]
    streets = gpd.read_file(ROOT / "assets" / "geo" / "bbr_streets.geojson")[["street_id", "susceptibility"]]
    bundle = predict.bundle_for(ROOT / "models", START, live=False)
    expected = set()
    for step in replay.run(START, END, STEP, readings, stations, streets, station_ids, rules_cfg, matrix_cfg,
                           ml_bundle=bundle, ml_cfg=_cfg("ml.yaml"), wl_ids=wl_ids, tide=None, street_stations=mapping):
        expected |= {(a.street_id, a.level.json, a.kind, a.issued_at) for a in step.alerts}
    assert {(r.street_id, r.level, r.kind, r.issued_at) for r in rows} == expected


def test_rerun_replaces_not_duplicates(conn, readings, stations, mapping):
    first = _run(conn, readings, stations, mapping)
    n = len(_rows(conn))
    second = _run(conn, readings, stations, mapping)
    assert len(_rows(conn)) == n and first == second
    assert conn.execute(select(func.count()).select_from(schema.street_state)).scalar() == 0   # alerts only


def test_rerun_keeps_other_months(conn, readings, stations, mapping):
    _run(conn, readings, stations, mapping)
    other_id = "BBR-x@20241001T0000-alert~backfill"
    conn.execute(schema.alerts.insert(), [dict(
        alert_id=other_id, street_id="BBR-x", township_id="BBR", horizon="nowcast", level="watch", kind="alert",
        issued_at=datetime(2024, 10, 1), window_start=None, window_end=None, fired_by_json="[]", reasons_json="[]",
        inputs_json=None, recipients=0, is_replay=False, is_backfill=True)])
    _run(conn, readings, stations, mapping)
    assert conn.execute(select(func.count()).select_from(schema.alerts).where(schema.alerts.c.alert_id == other_id)).scalar() == 1


def test_months_split_at_boundaries():
    chunks = backfill._months(datetime(2024, 11, 28, 6), datetime(2025, 1, 3, 12), STEP)
    assert chunks == [
        (datetime(2024, 11, 28, 6), datetime(2024, 11, 30, 23, 45)),
        (datetime(2024, 12, 1), datetime(2024, 12, 31, 23, 45)),
        (datetime(2025, 1, 1), datetime(2025, 1, 3, 12))]


def test_fold_model_is_the_one_that_never_trained_on_the_quarter():
    for month in (datetime(2024, 11, 1), datetime(2025, 2, 1), datetime(2026, 7, 1)):
        bundle, fold = backfill.oof_bundle(ROOT / "models", month)
        assert bundle["out_of_sample"] and fold == int(dataset.fold_of([month])[0])


def test_fold_mismatch_raises(monkeypatch):
    monkeypatch.setattr(backfill, "_excluded_fold", lambda models_dir, fold: (fold + 1) % 4)
    with pytest.raises(RuntimeError, match="fold"):
        backfill.oof_bundle(ROOT / "models", datetime(2024, 11, 1))


def test_final_model_is_refused(monkeypatch):
    monkeypatch.setattr(predict, "bundle_for", lambda *a, **k: {"model": None, "features": [], "out_of_sample": False})
    with pytest.raises(RuntimeError, match="out-of-fold"):
        backfill.oof_bundle(ROOT / "models", datetime(2024, 11, 1))


def test_each_step_asserts_fold(conn, readings, stations, mapping, monkeypatch):
    real, _ = backfill.oof_bundle(ROOT / "models", START)
    monkeypatch.setattr(backfill, "oof_bundle", lambda models_dir, when: (real, 1))   # wrong fold for Nov 2024 (fold 3)
    with pytest.raises(RuntimeError, match="fold"):
        _run(conn, readings, stations, mapping)
