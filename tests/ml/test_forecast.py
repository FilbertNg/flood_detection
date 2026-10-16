from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from floodready.ml import dataset, forecast

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "engine"
FEATS = ["rise_15m", "rise_60m", "d_warning"]


def synthetic(n=600, seed=0, start="2024-01-01"):
    """One station; the level follows a noisy walk so the future change is partly predictable."""
    rng = np.random.default_rng(seed)
    t = pd.date_range(start, periods=n, freq="15min")
    wl = np.cumsum(rng.normal(0, 0.03, n)) + 2.0
    s = pd.Series(wl)
    return pd.DataFrame({"graph_id": "A", "time_local": t, "wl_m": wl, "wl_warning_m": 4.0,
                         "rise_15m": s.diff(1), "rise_60m": s.diff(4), "d_warning": s - 4.0})


def test_targets_are_future_change_and_nan_past_the_end():
    t = forecast.add_targets(synthetic(50))
    assert t.d1h.iloc[0] == pytest.approx(t.wl_m.iloc[4] - t.wl_m.iloc[0])
    assert t.d2h.iloc[0] == pytest.approx(t.wl_m.iloc[8] - t.wl_m.iloc[0])
    assert t.d1h.iloc[-4:].isna().all() and t.d2h.iloc[-8:].isna().all()


def test_training_rows_keep_any_level_and_known_futures_only():
    t = synthetic(60)
    t.loc[10, "wl_m"] = np.nan
    t.loc[30, "wl_m"] = 4.5                          # above warning: still a training row
    rows = forecast.training_rows(forecast.add_targets(t))
    assert not rows.wl_m.isna().any() and not rows.d2h.isna().any()
    assert (rows.wl_m == 4.5).any() and "fold" in rows


@pytest.fixture(scope="module")
def bundle():
    rows = forecast.training_rows(forecast.add_targets(synthetic(900)))
    return forecast.fit(rows, FEATS)


def test_quantiles_never_cross(bundle):
    X = synthetic(200, seed=5)[FEATS]
    for h in forecast.HORIZONS:
        q = forecast.predict_changes(bundle, X)[h]
        assert (q[:, 0] <= q[:, 1]).all() and (q[:, 1] <= q[:, 2]).all()


def test_bundle_round_trip(bundle, tmp_path):
    path = tmp_path / "f.joblib"
    forecast.save_bundle(bundle, path)
    loaded = forecast.load_or_none(path)
    X = synthetic(50, seed=2)[FEATS]
    for h in forecast.HORIZONS:
        assert np.allclose(forecast.predict_changes(bundle, X)[h], forecast.predict_changes(loaded, X)[h])
    assert loaded["features"] == FEATS
    assert forecast.load_or_none(tmp_path / "missing.joblib") is None


def test_river_forecast_shape_and_values(bundle):
    t = synthetic(300, seed=3)
    at = t.time_local.iloc[200]
    out = forecast.river_forecast(bundle, t, "A", at.to_pydatetime())
    assert out["graph_id"] == "A"
    assert out["wl_now_m"] == pytest.approx(round(t.wl_m.iloc[200], 2))
    assert [p["time"] for p in out["points"]] == [
        (at + pd.Timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%S+08:00") for h in (1, 2)]
    for p in out["points"]:
        assert p["wl_m_p10"] <= p["wl_m"] <= p["wl_m_p90"]


def test_no_look_ahead(bundle):
    full = synthetic(300, seed=4)
    at = full.time_local.iloc[150]
    a = forecast.river_forecast(bundle, full, "A", at.to_pydatetime())
    changed = full.copy()
    changed.loc[changed.time_local > at, FEATS + ["wl_m"]] = 99.0
    b = forecast.river_forecast(bundle, changed, "A", at.to_pydatetime())
    assert a == b


def test_none_when_level_unknown_or_station_missing(bundle):
    t = synthetic(100)
    t.loc[50, "wl_m"] = np.nan
    assert forecast.river_forecast(bundle, t, "A", t.time_local.iloc[50].to_pydatetime()) is None
    assert forecast.river_forecast(bundle, t, "ZZZ", t.time_local.iloc[10].to_pydatetime()) is None
    assert forecast.river_forecast(bundle, t, "A", datetime(2030, 1, 1)) is None   # no row near `at`


def test_out_of_fold_forecast_is_not_scored_in_sample():
    rows = forecast.training_rows(forecast.add_targets(
        pd.concat([synthetic(500, seed=1, start=f"{y}-{m:02d}-01") for y, m in
                   [(2024, 1), (2024, 4), (2024, 7), (2024, 10)]], ignore_index=True)))
    models: dict = {}
    oof = forecast.cross_val_changes(rows, FEATS, models_out=models)
    assert set(models) == set(rows.fold.unique())
    assert oof["1h_p50"].notna().all()
    for fold, b in models.items():                    # a fold model never trained on its own fold
        assert fold not in b["trained_folds"]


def test_bundle_for_picks_fold_model_when_replaying(tmp_path):
    rows = forecast.training_rows(forecast.add_targets(synthetic(300)))
    b = forecast.fit(rows, FEATS)
    when = datetime(2024, 11, 12, 9, 0)
    fold = int(dataset.fold_of(pd.Series([pd.Timestamp(when)]))[0])
    forecast.save_bundle({**b, "tag": "final"}, tmp_path / "forecast_v1.joblib")
    forecast.save_bundle({**b, "tag": f"oof{fold}"}, tmp_path / f"forecast_v1_oof{fold}.joblib")
    assert forecast.bundle_for(tmp_path, when, live=True)["tag"] == "final"
    r = forecast.bundle_for(tmp_path, when, live=False)
    assert r["tag"] == f"oof{fold}" and r["out_of_sample"] is True
    (tmp_path / f"forecast_v1_oof{fold}.joblib").unlink()
    r = forecast.bundle_for(tmp_path, when, live=False)           # no fold model: fall back to the final one
    assert r["tag"] == "final" and r["out_of_sample"] is False
    assert forecast.bundle_for(tmp_path / "nope", when, live=True) is None


def test_works_on_real_features(monkeypatch):
    monkeypatch.setattr(forecast, "MODEL_PARAMS", {**forecast.MODEL_PARAMS, "min_samples_leaf": 2, "max_iter": 20})
    readings = pd.read_csv(FIX / "bbr_20241112_readings.csv", parse_dates=["time_local"], dtype={"graph_id": str})
    stations = pd.read_csv(FIX / "stations.csv", dtype={"graph_id": str, "station_code": str})
    feats = dataset.build_features(readings, stations, wl_ids=["PEKANMERU"])
    rows = forecast.training_rows(forecast.add_targets(feats))
    usable = [c for c in dataset.FEATURES if rows[c].notna().any()]       # no tide in this fixture
    b = forecast.fit(rows, usable)
    out = forecast.river_forecast(b, feats, "PEKANMERU", datetime(2024, 11, 12, 9, 0))
    assert out["wl_now_m"] == pytest.approx(3.52)
    assert out["warning_m"] == pytest.approx(4.0)


# ---------- serving robustness ----------

def test_missing_feature_column_gives_none_and_one_warning(bundle, caplog):
    t = synthetic(300, seed=3).drop(columns=["rise_60m"])
    with caplog.at_level("WARNING"):
        assert forecast.river_forecast(bundle, t, "A", t.time_local.iloc[200].to_pydatetime()) is None
    assert len([r for r in caplog.records if "missing features" in r.message]) == 1


def test_response_carries_the_reading_time(bundle):
    t = synthetic(300, seed=3)
    at = t.time_local.iloc[200]
    out = forecast.river_forecast(bundle, t, "A", at.to_pydatetime())
    assert out["wl_now_time"] == at.strftime("%Y-%m-%dT%H:%M:%S+08:00")


def _readings(wl_by_station, end="2024-11-12 09:00", n=12):
    t = pd.date_range(end=end, periods=n, freq="15min")
    return pd.concat([pd.DataFrame({"graph_id": g, "kind": "wl", "time_local": t, "wl_m": v, "rain_15min_mm": np.nan})
                      for g, v in wl_by_station.items()], ignore_index=True)


STATIONS = pd.DataFrame({"graph_id": ["A", "B", "C"], "kind": "wl", "wl_warning_m": [4.0, 4.0, 4.0]})
NOW = datetime(2024, 11, 12, 9, 0)


def test_pick_station_prefers_closest_to_its_warning_level_and_fresh_readings():
    flat = [-0.78] * 12
    near = list(np.linspace(3.0, 3.8, 12))
    r = _readings({"A": flat, "B": near})
    assert forecast.pick_station(r, STATIONS, ["A", "B"], NOW) == "B"
    stale = pd.concat([_readings({"B": near}, end="2024-11-12 08:15"), _readings({"A": flat})], ignore_index=True)
    assert forecast.pick_station(stale, STATIONS, ["A", "B"], NOW) == "A"          # B's last reading is 45 min old
    assert forecast.pick_station(r.iloc[0:0], STATIONS, ["A", "B"], NOW) is None


def test_pick_station_ties_go_to_the_faster_rise():
    r = _readings({"A": [3.0] * 12, "B": list(np.linspace(2.0, 3.0, 12))})
    assert forecast.pick_station(r, STATIONS, ["A", "B"], NOW) == "B"


def test_forecast_from_readings_needs_a_level_at_most_30_min_old(bundle):
    r = _readings({"A": list(np.linspace(2.0, 3.0, 12))})
    st = STATIONS.assign(lat=3.0, lon=101.0, thresholds_ok=True, wl_normal_m=1.0, wl_alert_m=3.5, wl_danger_m=4.5)
    assert forecast.forecast_from_readings(bundle, r, st, None, "A", datetime(2024, 11, 12, 9, 45)) is None


def test_bundle_records_rain_gauges_and_tide_signature():
    rows = forecast.training_rows(forecast.add_targets(synthetic(300)))
    tide = pd.DataFrame({"time_local": pd.date_range("2024-01-01", periods=10, freq="h"), "tide_height_m": np.arange(10.0)})
    b = forecast.fit(rows, FEATS, rain_ids=["R2", "R1"], tide=tide)
    assert b["rain_ids"] == ["R1", "R2"]
    assert b["tide_signature"]["rows"] == 10
    changed = tide.assign(tide_height_m=tide.tide_height_m + 0.1)
    assert forecast.tide_signature(changed) != b["tide_signature"]
    assert forecast.fit(rows, FEATS)["rain_ids"] is None


def test_serving_uses_only_the_trained_rain_gauges(bundle, monkeypatch):
    seen = []
    t = synthetic(300, seed=3)
    monkeypatch.setattr(forecast.dataset, "build_features", lambda r, *a, **k: seen.append(set(r.graph_id)) or t)
    last = t.time_local.iloc[200]
    r = pd.concat([_readings({"A": [3.0] * 12}, end=str(last)),
                   pd.DataFrame({"graph_id": ["R1", "R9"], "kind": "rf", "time_local": last, "wl_m": np.nan, "rain_15min_mm": 1.0})])
    forecast.forecast_from_readings({**bundle, "rain_ids": ["R1"]}, r, STATIONS, None, "A", last.to_pydatetime())
    assert seen == [{"A", "R1"}]


def test_bundle_cache_retries_a_missing_model_and_picks_fold_models(bundle, tmp_path):
    clock = [0.0]
    cache = forecast.BundleCache(tmp_path, retry_s=300, clock=lambda: clock[0])
    when = datetime(2024, 11, 12, 9, 0)
    assert cache.get(when, True) is None
    forecast.save_bundle({**bundle, "tag": "final"}, tmp_path / "forecast_v1.joblib")
    clock[0] = 100
    assert cache.get(when, True) is None                       # still within the retry window
    clock[0] = 301
    assert cache.get(when, True)["tag"] == "final"
    fold = int(dataset.fold_of(pd.Series([pd.Timestamp(when)]))[0])
    forecast.save_bundle({**bundle, "tag": "oof"}, tmp_path / f"forecast_v1_oof{fold}.joblib")
    assert cache.get(when, False)["tag"] == "oof"


def test_bundle_cache_live_and_fold_one_do_not_share_a_slot(bundle, tmp_path):
    final = {**bundle, "trained_folds": [0, 1, 2, 3]}
    oof1 = {**bundle, "trained_folds": [0, 2, 3]}
    forecast.save_bundle(final, tmp_path / "forecast_v1.joblib")
    forecast.save_bundle(oof1, tmp_path / "forecast_v1_oof1.joblib")
    q2 = datetime(2024, 5, 1)                      # fold 1
    assert int(dataset.fold_of(pd.Series([pd.Timestamp(q2)]))[0]) == 1
    a = forecast.BundleCache(tmp_path)
    assert a.get(q2, True)["trained_folds"] == [0, 1, 2, 3]
    assert 1 not in a.get(q2, False)["trained_folds"]
    b = forecast.BundleCache(tmp_path)
    assert 1 not in b.get(q2, False)["trained_folds"]
    assert b.get(q2, True)["trained_folds"] == [0, 1, 2, 3]
