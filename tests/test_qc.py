from pathlib import Path

import numpy as np
import pandas as pd

from floodready import qc

FIXTURES = Path(__file__).parent / "fixtures" / "qc"
T0 = pd.Timestamp("2025-03-01 00:00")


def rain(graph_id, values, start=T0, step_min=15):
    times = [start + pd.Timedelta(minutes=step_min * i) for i in range(len(values))]
    return pd.DataFrame({"graph_id": graph_id, "kind": "rf", "time_local": times,
                         "rain_15min_mm": values, "wl_m": np.nan})


def level(graph_id, values, start=T0):
    times = [start + pd.Timedelta(minutes=15 * i) for i in range(len(values))]
    return pd.DataFrame({"graph_id": graph_id, "kind": "wl", "time_local": times,
                         "rain_15min_mm": np.nan, "wl_m": values})


def rules_of(flags):
    return sorted(flags.rule.tolist())


def test_negative_and_implausible_rain_become_nan_not_zero():
    df = rain("A", [0.0, -3.0, 2.0, 150.0, 100.0, 1.0])
    clean, flags = qc.clean_readings(df)
    assert clean.rain_15min_mm.isna().tolist() == [False, True, False, True, False, False]
    assert clean.rain_15min_mm.tolist()[4] == 100.0          # exactly the limit is kept
    assert rules_of(flags) == ["rain_implausible", "rain_negative"]
    assert set(flags.columns) == {"graph_id", "kind", "time_local", "value", "rule"}
    assert flags.set_index("rule").value.to_dict() == {"rain_negative": -3.0, "rain_implausible": 150.0}
    assert df.rain_15min_mm.iloc[1] == -3.0                  # input untouched


def test_genuine_heavy_rain_survives():
    df = rain("A", [0.0, 12.0, 61.0, 95.0, 40.0, 0.0])
    clean, flags = qc.clean_readings(df)
    assert flags.empty
    pd.testing.assert_frame_equal(clean, df)


def test_rain_after_gap_flags_catch_up_but_not_short_gaps():
    # 2 h 15 min with no reading (8 missing slots), then 36 mm
    gap = pd.concat([rain("A", [0.0, 0.0]), rain("A", [36.0, 1.0], start=T0 + pd.Timedelta(minutes=15 * 10))],
                    ignore_index=True)
    clean, flags = qc.clean_readings(gap)
    assert rules_of(flags) == ["rain_after_gap"]
    assert np.isnan(clean.rain_15min_mm.iloc[2]) and clean.rain_15min_mm.iloc[3] == 1.0

    # same gap expressed as NaN rows (the archive grid): same result
    nan_rows = rain("A", [0.0, 0.0] + [np.nan] * 8 + [36.0, 1.0])
    _, flags2 = qc.clean_readings(nan_rows)
    assert rules_of(flags2) == ["rain_after_gap"]

    # a gap shorter than 2 h, or a value below 30 mm, is left alone
    short = pd.concat([rain("A", [0.0]), rain("A", [45.0], start=T0 + pd.Timedelta(minutes=15 * 8))], ignore_index=True)
    assert qc.clean_readings(short)[1].empty
    small = pd.concat([rain("A", [0.0]), rain("A", [29.5], start=T0 + pd.Timedelta(hours=10))], ignore_index=True)
    assert qc.clean_readings(small)[1].empty


def test_storm_that_started_during_a_gap_is_kept():
    df = pd.concat([rain("A", [0.0]), rain("A", [30.5, 24.0, 11.5], start=T0 + pd.Timedelta(hours=10))],
                   ignore_index=True)
    clean, flags = qc.clean_readings(df)
    assert flags.empty and clean.rain_15min_mm.tolist() == [0.0, 30.5, 24.0, 11.5]


def test_first_reading_of_a_gauge_is_never_a_gap_catch_up():
    assert qc.clean_readings(rain("A", [40.0, 0.0]))[1].empty


def test_stuck_repeat_flags_all_copies_within_24h():
    vals = [0.0, 33.5, 0.0, 33.5, 0.0, 0.0, 33.5, 0.0]
    clean, flags = qc.clean_readings(rain("A", vals))
    assert rules_of(flags) == ["rain_stuck"] * 3
    assert clean.rain_15min_mm.tolist()[1] != clean.rain_15min_mm.tolist()[1]  # NaN
    assert clean.rain_15min_mm.isna().sum() == 3


def test_stuck_needs_three_copies_20mm_and_one_gauge_and_24h():
    two = rain("A", [25.0, 0.0, 25.0, 0.0])
    assert qc.clean_readings(two)[1].empty
    small = rain("A", [5.0, 5.0, 5.0, 5.0])                  # repeated drizzle is normal
    assert qc.clean_readings(small)[1].empty
    other_gauges = pd.concat([rain("A", [25.0]), rain("B", [25.0]), rain("C", [25.0])], ignore_index=True)
    assert qc.clean_readings(other_gauges)[1].empty
    spread = pd.concat([rain("A", [25.0], start=T0 + pd.Timedelta(hours=13 * i)) for i in range(3)], ignore_index=True)
    assert qc.clean_readings(spread)[1].empty                # 3 copies over 26 h: not within 24 h
    inside = pd.concat([rain("A", [25.0], start=T0 + pd.Timedelta(hours=11 * i)) for i in range(3)], ignore_index=True)
    assert rules_of(qc.clean_readings(inside)[1]) == ["rain_stuck"] * 3


def test_first_matching_rule_wins_and_each_reading_is_flagged_once():
    df = rain("A", [300.0, 300.0, 300.0])
    _, flags = qc.clean_readings(df)
    assert rules_of(flags) == ["rain_implausible"] * 3


def test_river_spike_that_reverses_is_flagged():
    df = level("R", [3.0, 3.1, 5.2, 3.2, 3.3])
    clean, flags = qc.clean_readings(df)
    assert rules_of(flags) == ["wl_spike"]
    assert flags.value.iloc[0] == 5.2
    assert np.isnan(clean.wl_m.iloc[2]) and clean.wl_m.iloc[3] == 3.2


def test_real_rise_and_negative_levels_are_kept():
    rise = level("R", [3.0, 3.1, 4.5, 4.6, 4.7])             # jumps 1.4 m and stays up: a real rise
    assert qc.clean_readings(rise)[1].empty
    tidal = level("T", [-0.5, -1.0, -1.6, -1.1, -0.4])      # negative levels (datum below sea level)
    clean, flags = qc.clean_readings(tidal)
    assert flags.empty and clean.wl_m.tolist() == tidal.wl_m.tolist()
    small = level("R", [3.0, 3.8, 3.1])                      # 0.8 m blip is under the 1.0 m threshold
    assert qc.clean_readings(small)[1].empty


def test_kinds_do_not_leak_into_each_other():
    df = pd.concat([rain("A", [-5.0, 1.0]), level("A", [2.0, 2.1])], ignore_index=True)
    clean, flags = qc.clean_readings(df)
    assert flags.kind.tolist() == ["rf"]
    assert clean.wl_m.dropna().tolist() == [2.0, 2.1]


def test_empty_input():
    empty = pd.DataFrame(columns=qc.COLUMNS)
    clean, flags = qc.clean_readings(empty)
    assert clean.empty and flags.empty and list(flags.columns) == qc.FLAG_COLUMNS


def test_12_nov_2024_storm_is_untouched():
    storm = pd.read_parquet(FIXTURES / "storm_20241112.parquet")
    assert {"PEKANMERU"} <= set(storm.graph_id) and storm.rain_15min_mm.max() > 20 and storm.wl_m.max() > 4.2
    clean, flags = qc.clean_readings(storm)
    assert flags.empty
    pd.testing.assert_frame_equal(clean, storm)
