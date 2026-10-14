from datetime import datetime

import pandas as pd

from floodready import live

T = lambda hhmm, day=14: datetime(2026, 10, day, int(hhmm[:2]), int(hhmm[3:]))  # noqa: E731


def test_rain_per_quarter_is_the_difference_of_rain_since_midnight():
    rf = pd.DataFrame({
        "graph_id": ["26558"] * 4, "source_time": [T("08:00"), T("08:15"), T("08:30"), T("08:30")],
        "rain_since_midnight_mm": [10.0, 14.0, 20.5, 20.5],            # last row: same reading logged twice
    })
    out = live.rain_readings(rf).set_index("time_local")
    assert out.loc[T("08:15"), "rain_15min_mm"] == 4.0
    assert out.loc[T("08:30"), "rain_15min_mm"] == 6.5
    assert len(out) == 2                                              # first reading has no previous value


def test_midnight_reset_counts_the_new_days_total():
    rf = pd.DataFrame({"graph_id": ["X"] * 2, "source_time": [T("23:45", 14), T("00:00", 15)],
                       "rain_since_midnight_mm": [30.0, 1.5]})
    out = live.rain_readings(rf)
    assert out.rain_15min_mm.tolist() == [1.5]


def test_water_level_readings_keep_the_source_time():
    wl = pd.DataFrame({"graph_id": ["PEKANMERU"] * 2, "source_time": [T("19:30"), T("19:45")], "wl_m": [3.2, None]})
    out = live.level_readings(wl)
    assert out.kind.unique().tolist() == ["wl"] and out.wl_m.tolist()[0] == 3.2
    assert set(out.columns) == {"graph_id", "kind", "time_local", "rain_15min_mm", "wl_m"}


def test_a_corrected_live_reading_replaces_the_placeholder():
    wl = pd.DataFrame({"graph_id": ["PEKANMERU"] * 2, "source_time": [T("01:00")] * 2, "wl_m": [0.0, 3.15],
                       "fetched_at_local": [T("01:02"), T("01:16")]})
    assert live.level_readings(wl).wl_m.tolist() == [3.15]
