"""v2 features: pruning, tidal coupling, upstream stations."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from floodready.ml import dataset
from floodready.tide import tide_at

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
    tide_q = tide_at(tide, grid).tide_height_m.to_numpy()
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


def test_tide_coupling_is_nan_not_inf_for_a_flat_level_and_stays_in_range():
    r, s, tide = _synthetic()
    r.loc[r.graph_id == "A", "wl_m"] = 1.5
    c = dataset.build_features(r, s, tide, ["A"], network={}).tide_coupling_3d
    assert not np.isinf(c).any() and c.isna().all()
    r, s, tide = _synthetic()
    c = dataset.build_features(r, s, tide, ["A"], network={}).tide_coupling_3d.dropna()
    assert c.between(-1, 1).all()


def test_no_feature_looks_ahead_even_when_tide_changes_after_the_cut():
    r, s, tide = _synthetic()
    # The cut falls on a whole table hour, so tide interpolation reads no later table value here. At a cut between
    # hours the tide legitimately reads the next table hour (a forecast known at t, see tide_at); that case is
    # covered by test_no_observation_column_uses_data_after_t_at_a_non_whole_hour_cut. Do not "fix" this test.
    cut = pd.Timestamp("2024-03-04 00:00")
    net = {"A": ["B"]}
    before = dataset.build_features(r, s, tide, ["A"], network=net)
    r2, t2 = r.copy(), tide.copy()
    r2.loc[r2.time_local > cut, "wl_m"] = 50.0
    t2.loc[t2.time_local > cut, "tide_height_m"] = 99.0
    after = dataset.build_features(r2, s, t2, ["A"], network=net)
    cols = [c for c in dataset.FEATURES if c != "hours_to_high_tide"]
    pd.testing.assert_frame_equal(before[before.time_local <= cut][cols].reset_index(drop=True),
                                  after[after.time_local <= cut][cols].reset_index(drop=True))


def test_self_links_and_duplicates_are_ignored_in_features():
    r, s, tide = _synthetic()
    a = dataset.build_features(r, s, tide, ["A"], network={"A": ["B"]})
    b = dataset.build_features(r, s, tide, ["A"], network={"A": ["A", "B", "B"]})
    pd.testing.assert_frame_equal(a, b)


def _tide_table(hours=48, period=12.4):
    """Hourly tide like data/interim/tide_hourly.parquet: height plus signed hours to the nearest high water."""
    idx = pd.date_range("2024-03-01", periods=hours, freq="h")
    h = np.asarray((idx - idx[0]) / pd.Timedelta(hours=1))
    height = 2.0 + 1.5 * np.sin(2 * np.pi * h / period)
    highs = period / 4 + period * np.arange(-1, 6)         # hours after idx[0]
    rel = []
    for x in h:
        d = highs - x
        nxt, prv = d[d >= 0].min(), d[d < 0].max()
        rel.append(nxt if nxt <= -prv else prv)
    return pd.DataFrame({"time_local": idx, "tide_height_m": height, "hours_to_high_tide": rel})


def test_tide_at_a_quarter_hour_is_between_the_hours_not_the_hour_floor():
    tide = _tide_table()
    grid = pd.DatetimeIndex(["2024-03-01 03:00", "2024-03-01 03:45", "2024-03-01 04:00"])
    got = tide_at(tide, grid).tide_height_m.to_numpy()
    h = tide.set_index("time_local").tide_height_m
    assert got[0] == pytest.approx(h["2024-03-01 03:00"]) and got[2] == pytest.approx(h["2024-03-01 04:00"])
    assert abs(got[1] - got[0]) > 0.05                                     # moving tide: not the 03:00 value
    assert got[1] == pytest.approx(0.25 * h["2024-03-01 03:00"] + 0.75 * h["2024-03-01 04:00"])
    true = 2.0 + 1.5 * np.sin(2 * np.pi * 3.75 / 12.4)                     # and close to the true curve between the hours
    assert abs(got[1] - true) < 0.06


def test_hours_to_high_tide_counts_down_within_the_hour():
    tide = _tide_table()
    t = pd.DatetimeIndex(["2024-03-01 01:00", "2024-03-01 01:15", "2024-03-01 01:30", "2024-03-01 01:45"])
    got = tide_at(tide, t).hours_to_high_tide.to_numpy()
    assert np.diff(got) == pytest.approx([-0.25] * 3)                      # high water at 03:06


def test_build_features_gives_each_quarter_its_own_tide_and_change():
    r, s, tide = _synthetic()
    f = dataset.build_features(r, s, tide, ["A"], network={}).set_index("time_local")
    t = pd.Timestamp("2024-03-01 09:45")
    assert abs(f.tide_height_m[t] - f.tide_height_m[t.floor("h")]) > 0.05
    assert abs(f.tide_change_1h[t] - f.tide_change_1h[t.floor("h")]) > 0.01
    assert f.tide_height_m[t] == pytest.approx(tide_at(tide, pd.DatetimeIndex([t])).tide_height_m.iloc[0])


def test_tide_features_do_not_depend_on_what_else_is_in_the_window():
    """Train / replay / live all call build_features on different windows: the tide columns for a timestamp must agree."""
    r, s, tide = _synthetic()
    full = dataset.build_features(r, s, tide, ["A"], network={}).set_index("time_local")
    cols = ["tide_height_m", "hours_to_high_tide", "tide_change_1h"]
    live = dataset.build_features(r[r.time_local <= pd.Timestamp("2024-03-02 06:45")], s, tide, ["A"], network={}).set_index("time_local")
    pd.testing.assert_frame_equal(full.loc[live.index, cols], live[cols])
    replay = dataset.build_features(r[r.time_local > pd.Timestamp("2024-03-01 12:10")], s, tide, ["A"], network={}).set_index("time_local")
    pd.testing.assert_frame_equal(full.loc[replay.index, cols].iloc[4:], replay[cols].iloc[4:])


def test_tide_does_not_bridge_a_gap_or_read_past_the_table():
    tide = _tide_table(hours=10)
    tide.loc[4:5, "tide_height_m"] = np.nan
    got = tide_at(tide, pd.DatetimeIndex(["2024-03-01 04:30", "2024-03-01 05:30", "2024-03-01 09:30", "2024-03-01 11:00"]))
    assert got.tide_height_m.isna().all()
    assert tide_at(tide, pd.DatetimeIndex(["2024-03-01 02:30"])).tide_height_m.notna().all()


def test_observation_columns_at_t_ignore_later_readings():
    r, s, tide = _synthetic()
    cut = pd.Timestamp("2024-03-01 09:45")
    base = dataset.build_features(r, s, tide, ["A"], network={})
    changed = r.copy()
    changed.loc[changed.time_local > cut, "wl_m"] = 50.0
    after = dataset.build_features(changed, s, tide, ["A"], network={})
    obs = ["wl_m", "d_warning", "level_rel", "rise_15m", "rise_60m", "rise_120m", "tide_coupling_3d",
           "tide_height_m", "hours_to_high_tide", "tide_change_1h"]
    m = base.time_local <= cut
    pd.testing.assert_frame_equal(base[m][obs].reset_index(drop=True), after[m][obs].reset_index(drop=True))


@pytest.mark.parametrize("unit", ["ns", "us", "ms", "s"])
def test_tide_at_is_independent_of_the_datetime_units_of_table_and_grid(unit):
    tide = _tide_table()
    tide["time_local"] = tide.time_local.astype("datetime64[us]")
    grid = pd.date_range("2024-03-01 03:00", periods=9, freq="15min").as_unit(unit)
    got = tide_at(tide, grid)
    ref = tide_at(_tide_table(), pd.date_range("2024-03-01 03:00", periods=9, freq="15min"))
    assert got.tide_height_m.notna().all()
    np.testing.assert_allclose(got.tide_height_m.to_numpy(), ref.tide_height_m.to_numpy())
    np.testing.assert_allclose(got.hours_to_high_tide.to_numpy(), ref.hours_to_high_tide.to_numpy())


def test_tide_does_not_bridge_a_missing_row():
    tide = _tide_table(hours=10).drop(index=4)          # the 04:00 row is absent (not NaN): 03:00 and 05:00 are 2 h apart
    got = tide_at(tide, pd.DatetimeIndex(["2024-03-01 03:30", "2024-03-01 04:30", "2024-03-01 03:00", "2024-03-01 05:00", "2024-03-01 06:30"]))
    assert got.tide_height_m.isna().tolist() == [True, True, False, False, False]


def test_no_observation_column_uses_data_after_t_at_a_non_whole_hour_cut():
    """The cut sits at 09:45, between two table hours. Tide may read the 10:00 table value (a forecast, known at t);
    every observation-derived column must not read anything after 09:45."""
    r, s, tide = _synthetic()
    cut = pd.Timestamp("2024-03-01 09:45")
    base = dataset.build_features(r, s, tide, ["A"], network={"A": ["B"]})
    changed = r.copy()
    changed.loc[changed.time_local > cut, ["wl_m", "rain_15min_mm"]] = 50.0
    after = dataset.build_features(changed, s, tide, ["A"], network={"A": ["B"]})
    obs = [c for c in dataset.FEATURES if not c.startswith("tide_") and c != "hours_to_high_tide"] + ["wl_m", "tide_coupling_3d"]
    m = base.time_local <= cut
    assert (base.time_local == cut).any()
    pd.testing.assert_frame_equal(base[m][obs].reset_index(drop=True), after[m][obs].reset_index(drop=True))
