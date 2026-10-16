from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from floodready.ml import dataset

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "engine"
T = lambda hhmm: pd.Timestamp(datetime(2024, 11, 12, int(hhmm[:2]), int(hhmm[3:])))  # noqa: E731


@pytest.fixture(scope="module")
def readings():
    return pd.read_csv(FIX / "bbr_20241112_readings.csv", parse_dates=["time_local"], dtype={"graph_id": str})


@pytest.fixture(scope="module")
def stations():
    return pd.read_csv(FIX / "stations.csv", dtype={"graph_id": str, "station_code": str})


@pytest.fixture(scope="module")
def table(readings, stations):
    feats = dataset.build_features(readings, stations, wl_ids=["PEKANMERU"])
    return dataset.add_labels(feats)


def row(table, hhmm):
    return table[(table.graph_id == "PEKANMERU") & (table.time_local == T(hhmm))].iloc[0]


def test_features_are_relative_to_each_stations_own_thresholds(table):
    r = row(table, "09:00")                                        # Sg Binjai 3.52 m; alert 3.8 / warning 4.0 / danger 4.2
    assert r.d_warning == pytest.approx(3.52 - 4.0)
    assert r.level_rel == pytest.approx((3.52 - 2.8) / (4.2 - 2.8))
    assert r.rise_60m == pytest.approx(3.52 - 2.94)                # 08:00 -> 09:00


def test_rain_features_use_stations_within_the_radius(table, stations):
    r = row(table, "09:00")
    assert r.rain_1h_max_25km == 61.5                              # Kg Perepat is ~9 km from Pekan Meru
    assert np.isfinite(r.rain_2to4h_max_10km)


def test_label_says_whether_warning_level_is_crossed_ahead(table):
    assert row(table, "08:30").cross_2h == 1                       # reaches 4.06 m at 09:30
    assert row(table, "08:30").cross_1h == 1
    assert row(table, "07:00").cross_1h == 0
    assert row(table, "06:00").cross_2h == 0


def test_training_rows_exclude_times_already_at_or_above_warning(table):
    train = dataset.training_rows(table)
    pm = train[train.graph_id == "PEKANMERU"]
    assert T("10:00") not in set(pm.time_local)                    # 4.21 m: already above warning
    assert T("09:00") in set(pm.time_local)
    assert set(train.columns) >= set(dataset.FEATURES) | {"cross_1h", "cross_2h", "fold"}


def test_no_station_identity_among_features():
    assert not any("graph_id" in f or "station" in f for f in dataset.FEATURES)


def test_features_use_only_past_data(readings, stations):
    cut = T("09:00")
    before = dataset.build_features(readings, stations, wl_ids=["PEKANMERU"])
    changed = readings.copy()
    changed.loc[changed.time_local > cut, ["rain_15min_mm", "wl_m"]] = 999.0
    after = dataset.build_features(changed, stations, wl_ids=["PEKANMERU"])
    a = before[before.time_local <= cut].reset_index(drop=True)
    b = after[after.time_local <= cut].reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b)


def test_rain_stations_near_river_stations(stations):
    near = dataset.rain_stations_near(stations, ["PEKANMERU"], km=25)
    assert "26558" in near and "PEKANMERU" in near
    assert dataset.rain_stations_near(stations, ["PEKANMERU"], km=25, available={"26558"}) == ["26558"]
