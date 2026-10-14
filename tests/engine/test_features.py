from datetime import datetime

import numpy as np
import pandas as pd

from floodready.engine import features

T = lambda hhmm: datetime(2024, 11, 12, int(hhmm[:2]), int(hhmm[3:]))  # noqa: E731


def at(readings, stations, when):
    return features.station_features(readings, when, stations).set_index(["graph_id", "kind"])


def test_rolling_rain_at_kg_perepat_matches_the_real_storm(readings, stations):
    assert at(readings, stations, T("08:45")).loc[("26558", "rf"), "st_rain_1h"] == 45.0
    f = at(readings, stations, T("09:00")).loc[("26558", "rf")]
    assert f.st_rain_1h == 61.5
    assert f.st_rain_2to4h_max >= 61.5


def test_river_band_and_rise_at_sg_binjai(readings, stations):
    f930 = at(readings, stations, T("09:30")).loc[("PEKANMERU", "wl")]
    assert f930.wl_m == 4.06 and f930.river_band == "warning" and bool(f930.river_rising) is True
    f1000 = at(readings, stations, T("10:00")).loc[("PEKANMERU", "wl")]
    assert f1000.river_band == "danger"
    assert at(readings, stations, T("08:30")).loc[("PEKANMERU", "wl"), "river_band"] == "normal"


def test_missing_quarters_are_counted_not_hidden(stations):
    rows = [{"graph_id": "26558", "kind": "rf", "time_local": T("08:00") + pd.Timedelta(minutes=15 * k),
             "rain_15min_mm": v, "wl_m": np.nan} for k, v in enumerate([5.0, np.nan, 10.0, 2.0])]
    f = at(pd.DataFrame(rows), stations, T("08:45")).loc[("26558", "rf")]
    assert f.st_rain_1h == 17.0 and f.n_missing_1h == 1


def test_station_without_recent_readings_is_stale(stations):
    rows = [{"graph_id": "26558", "kind": "rf", "time_local": T("05:00"), "rain_15min_mm": 1.0, "wl_m": np.nan}]
    f = at(pd.DataFrame(rows), stations, T("09:00")).loc[("26558", "rf")]
    assert bool(f.is_stale) is True


def test_features_use_only_data_up_to_the_query_time(readings, stations):
    before = at(readings, stations, T("08:45"))
    future_changed = readings.copy()
    future_changed.loc[future_changed.time_local > T("08:45"), ["rain_15min_mm", "wl_m"]] = 999.0
    after = at(future_changed, stations, T("08:45"))
    pd.testing.assert_frame_equal(before, after)
