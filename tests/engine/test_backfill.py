"""WP5: backfill = replay.run month by month into the DB, out-of-fold ML, idempotent."""
import json
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
def eng():
    return repo.connect("sqlite://")


@pytest.fixture(scope="module")
def mapping():
    return street_stations.load(ROOT / "assets" / "geo" / "bbr_street_stations.json")


def _run(eng, readings, stations, mapping, start=START, end=END):
    return backfill.run_backfill(start, end, "BBR", eng, STEP, models_dir=ROOT / "models",
                                 readings=readings, stations=stations, tide=None, mapping=mapping)


def _rows(eng):
    a = schema.alerts
    with eng.connect() as conn:
        return conn.execute(select(a.c.alert_id, a.c.street_id, a.c.level, a.c.kind, a.c.issued_at, a.c.is_backfill,
                                   a.c.is_replay, a.c.reasons_json).order_by(a.c.alert_id)).all()


def test_matches_replay_run(eng, readings, stations, rules_cfg, matrix_cfg, mapping):
    _run(eng, readings, stations, mapping)
    rows = _rows(eng)
    assert rows
    assert all(r.is_backfill and not r.is_replay and r.alert_id.endswith("~backfill") for r in rows)

    town = next(t for t in _cfg("townships.yaml")["townships"] if t["id"] == "BBR")
    station_ids = [s["graph_id"] for s in town["stations"]]
    wl_ids = [s["graph_id"] for s in town["stations"] if "WL" in s.get("types", [])]
    streets = gpd.read_file(ROOT / "assets" / "geo" / "bbr_streets.geojson")[["street_id", "susceptibility"]]
    bundle = predict.bundle_for(ROOT / "models", START, live=False)
    ml_cfg = _cfg("ml.yaml")
    assert ml_cfg["ml_drives_alerts"] is False   # a gate flip would silently change backfill levels
    expected = set()
    for step in replay.run(START, END, STEP, readings, stations, streets, station_ids, rules_cfg, matrix_cfg,
                           ml_bundle=bundle, ml_cfg=ml_cfg, wl_ids=wl_ids, tide=None, street_stations=mapping):
        expected |= {(a.street_id, a.level.json, a.kind, a.issued_at, json.dumps([repo._reason_dict(x) for x in a.reasons])) for a in step.alerts}
    assert {(r.street_id, r.level, r.kind, r.issued_at, json.dumps(json.loads(r.reasons_json))) for r in rows} == expected


def test_rerun_replaces_not_duplicates(eng, readings, stations, mapping):
    first = _run(eng, readings, stations, mapping)
    n = len(_rows(eng))
    second = _run(eng, readings, stations, mapping)
    assert len(_rows(eng)) == n and first == second
    with eng.connect() as conn:
        assert conn.execute(select(func.count()).select_from(schema.street_state)).scalar() == 0   # alerts only


def test_rerun_keeps_other_months(eng, readings, stations, mapping):
    _run(eng, readings, stations, mapping)
    other_id = "BBR-x@20241001T0000-alert~backfill"
    with eng.begin() as conn:
        conn.execute(schema.alerts.insert(), [dict(
        alert_id=other_id, street_id="BBR-x", township_id="BBR", horizon="nowcast", level="watch", kind="alert",
            issued_at=datetime(2024, 10, 1), window_start=None, window_end=None, fired_by_json="[]", reasons_json="[]",
            inputs_json=None, recipients=0, is_replay=False, is_backfill=True)])
    _run(eng, readings, stations, mapping)
    with eng.connect() as conn:
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


def test_each_step_asserts_fold(eng, readings, stations, mapping, monkeypatch):
    real, _ = backfill.oof_bundle(ROOT / "models", START)
    monkeypatch.setattr(backfill, "oof_bundle", lambda models_dir, when: (real, 1))   # wrong fold for Nov 2024 (fold 3)
    with pytest.raises(RuntimeError, match="fold"):
        _run(eng, readings, stations, mapping)


def _split(monkeypatch, mid):
    """Treat the fixture day as two 'months' split at `mid` (month 2 starts there)."""
    monkeypatch.setattr(backfill, "_months", lambda start, end, step: [(START, mid - STEP), (mid, END)])


def test_failure_in_month_2_keeps_month_1(eng, readings, stations, mapping, monkeypatch):
    mid = datetime(2024, 11, 12, 10, 0)
    _split(monkeypatch, mid)
    calls = []
    real = backfill.oof_bundle

    def flaky(models_dir, when):
        calls.append(when)
        if len(calls) == 2:
            raise RuntimeError("month 2 failed")
        return real(models_dir, when)
    monkeypatch.setattr(backfill, "oof_bundle", flaky)
    with pytest.raises(RuntimeError, match="month 2"):
        _run(eng, readings, stations, mapping)
    rows = _rows(eng)
    assert rows and all(r.issued_at < mid for r in rows)


def test_no_restart_duplicates_at_month_start(eng, readings, stations, mapping, monkeypatch):
    """An alert opened in month 1 and still elevated at the first step of month 2 is not re-issued there."""
    whole = repo.connect("sqlite://")
    _run(whole, readings, stations, mapping)
    rows = _rows(whole)
    alerts = [r for r in rows if r.kind == "alert"]
    clears = [r for r in rows if r.kind != "alert"]
    mid = None
    for t in sorted({r.issued_at for r in alerts}):
        t_next = t + STEP
        if t_next >= END:
            break
        open_streets = {r.street_id for r in alerts if r.issued_at <= t} -             {r.street_id for r in clears if r.issued_at <= t_next}
        if open_streets:
            mid = t_next
            break
    assert mid is not None, "fixture has no alert open across a step"
    _split(monkeypatch, mid)
    _run(eng, readings, stations, mapping)
    assert [(r.alert_id, r.level, r.kind) for r in _rows(eng)] == [(r.alert_id, r.level, r.kind) for r in rows]
