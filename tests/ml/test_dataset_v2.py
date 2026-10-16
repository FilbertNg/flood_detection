"""v2 features: pruning, tidal coupling, upstream stations."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from floodready.ml import dataset

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "engine"
PRUNED = ["n_rf_10km", "n_rf_25km", "d_alert", "d_danger"]
UP = ["up_rise_60m_max", "up_rise_120m_max", "up_level_rel_max"]


@pytest.fixture(scope="module")
def stations():
    return pd.read_csv(FIX / "stations.csv", dtype={"graph_id": str, "station_code": str})


def test_pruned_features_are_gone_and_new_ones_present():
    f = dataset.FEATURES
    assert not set(PRUNED) & set(f)
    assert not any("_mean_" in x for x in f)
    assert {"d_warning", "level_rel", "tide_coupling_3d", "tide_change_1h", *UP} <= set(f)
    assert not any("upstream_count" in x or x.startswith("n_up") for x in f)
    assert len(f) == len(set(f))


def _synthetic(n=600, level_from_tide=True):
    """`n` quarter hours for two river stations: A (downstream) and B (upstream of A)."""
    grid = pd.date_range("2024-03-01", periods=n, freq="15min")
    tide = pd.DataFrame({"time_local": pd.date_range("2024-03-01", periods=n // 4 + 2, freq="h")})
    tide["tide_height_m"] = 2.0 + 1.5 * np.sin(2 * np.pi * np.arange(len(tide)) / 12.4)
    tide["hours_to_high_tide"] = 1.0
    rng = np.random.default_rng(0)
    tide_q = pd.Series(tide.tide_height_m.to_numpy(), index=tide.time_local).reindex(grid.floor("h")).to_numpy()
    a = (1.0 + 0.5 * tide_q) if level_from_tide else 1.0 + 0.3 * rng.standard_normal(n)
    b = 1.0 + rng.standard_normal(n).cumsum() / 20
    readings = pd.concat([pd.DataFrame({"graph_id": g, "kind": "wl", "time_local": grid, "wl_m": v, "rain_15min_mm": np.nan})
                          for g, v in (("A", a), ("B", b))], ignore_index=True)
    stations = pd.DataFrame({"graph_id": ["A", "B"], "kind": "wl", "name": ["a", "b"], "lat": [3.0, 3.1], "lon": [101.4, 101.5],
                             "wl_normal_m": 1.0, "wl_alert_m": 2.0, "wl_warning_m": 3.0, "wl_danger_m": 4.0, "thresholds_ok": True})
    return readings, stations, tide


def test_tide_coupling_high_when_level_follows_the_tide_low_when_rain_driven():
    r, s, tide = _synthetic(level_from_tide=True)
    assert dataset.build_features(r, s, tide, ["A"], network={}).tide_coupling_3d.dropna().iloc[-1] > 0.95
    r, s, tide = _synthetic(level_from_tide=False)
    assert abs(dataset.build_features(r, s, tide, ["A"], network={}).tide_coupling_3d.dropna().iloc[-1]) < 0.3


def test_tide_coupling_needs_96_pairs_and_tide_change_is_one_hour():
    r, s, tide = _synthetic()
    f = dataset.build_features(r, s, tide, ["A"], network={}).set_index("time_local")
    assert f.tide_coupling_3d.iloc[:95].isna().all() and f.tide_coupling_3d.iloc[96:].notna().any()
    t = f.index[100]
    assert f.tide_change_1h[t] == pytest.approx(f.tide_height_m[t] - f.tide_height_m[t - pd.Timedelta(hours=1)])


def test_tide_features_are_nan_without_tide():
    r, s, _ = _synthetic()
    f = dataset.build_features(r, s, None, ["A"], network={})
    assert f.tide_coupling_3d.isna().all() and f.tide_change_1h.isna().all()


def test_tide_coupling_uses_no_future_data():
    r, s, tide = _synthetic()
    cut = pd.Timestamp("2024-03-04 00:00")
    before = dataset.build_features(r, s, tide, ["A"], network={})
    changed = r.copy()
    changed.loc[changed.time_local > cut, "wl_m"] = 50.0
    after = dataset.build_features(changed, s, tide, ["A"], network={})
    cols = ["tide_coupling_3d", "tide_change_1h"]
    pd.testing.assert_frame_equal(before[before.time_local <= cut][cols].reset_index(drop=True),
                                  after[after.time_local <= cut][cols].reset_index(drop=True))


def test_upstream_features_take_the_max_over_upstream_stations():
    r, s, tide = _synthetic()
    f = dataset.build_features(r, s, tide, ["A"], network={"A": ["B"]}).set_index("time_local")
    b = r[r.graph_id == "B"].set_index("time_local").wl_m
    t = f.index[200]
    assert f.up_rise_60m_max[t] == pytest.approx(b[t] - b[t - pd.Timedelta(hours=1)])
    assert f.up_rise_120m_max[t] == pytest.approx(b[t] - b[t - pd.Timedelta(hours=2)])
    assert f.up_level_rel_max[t] == pytest.approx((b[t] - 1.0) / 3.0)


def test_upstream_features_nan_without_upstream_or_data():
    r, s, tide = _synthetic()
    assert dataset.build_features(r, s, tide, ["A"], network={})[UP].isna().all().all()
    only_a = dataset.build_features(r[r.graph_id == "A"], s, tide, ["A"], network={"A": ["B"]})
    assert only_a[UP].isna().all().all()


def test_upstream_features_use_no_future_data():
    r, s, tide = _synthetic()
    cut = pd.Timestamp("2024-03-04 00:00")
    before = dataset.build_features(r, s, tide, ["A"], network={"A": ["B"]})
    changed = r.copy()
    changed.loc[(changed.time_local > cut) & (changed.graph_id == "B"), "wl_m"] = 50.0
    after = dataset.build_features(changed, s, tide, ["A"], network={"A": ["B"]})
    pd.testing.assert_frame_equal(before[before.time_local <= cut][UP].reset_index(drop=True),
                                  after[after.time_local <= cut][UP].reset_index(drop=True))


def test_required_station_ids_adds_upstream_and_rain_gauges(stations):
    base = dataset.required_station_ids(stations, ["PEKANMERU"], network={})
    assert "PEKANMERU" in base and "26558" in base
    ids = dataset.required_station_ids(stations, ["PEKANMERU"], network={"PEKANMERU": ["UPSTREAM1", "UPSTREAM2"], "OTHER": ["Z"]})
    assert {"UPSTREAM1", "UPSTREAM2"} <= set(ids) and set(base) <= set(ids) and "Z" not in ids
    assert ids == sorted(set(ids))
