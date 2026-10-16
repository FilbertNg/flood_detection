"""Review fixes for PR 15: moving-river spikes, counter rebound, live semantics, duplicated catch-up."""
from datetime import datetime

import numpy as np
import pandas as pd

from floodready import live, qc
from tests.test_qc import level, rain, rules_of, T0


def test_spike_on_a_rising_limb_is_flagged_real_3014080():
    df = level("3014080_", [1.9, 2.40, -5.85, 2.70, 3.0])          # 2024-08-23, mid-rise
    clean, flags = qc.clean_readings(df)
    assert rules_of(flags) == ["wl_spike"] and np.isnan(clean.wl_m.iloc[2])


def test_spike_up_on_a_rising_limb_is_flagged_real_3016080():
    clean, flags = qc.clean_readings(level("3016080_", [9.9, 10.22, 13.08, 10.88, 11.2]))
    assert flags.value.tolist() == [13.08]


def test_real_fast_rise_is_not_a_spike():
    assert qc.clean_readings(level("R", [3.0, 3.2, 4.5, 5.8, 6.9]))[1].empty      # keeps climbing
    assert qc.clean_readings(level("R", [3.0, 3.2, 4.5, 4.4, 4.5]))[1].empty      # jump stays up


def test_latest_river_reading_is_kept_in_live_mode():
    clean, flags = qc.clean_readings(level("R", [3.0, 3.1, 3.2, 6.0]))
    assert flags.empty and clean.wl_m.iloc[-1] == 6.0


def test_counter_rebound_real_26352_values():
    vals = [0.0, -57.0, 0, 0, 0, 0, 56.5, 0, 1.0]
    clean, flags = qc.clean_readings(rain("26352", vals))
    assert rules_of(flags) == ["rain_counter_rebound", "rain_negative"]
    assert clean.rain_15min_mm.isna().sum() == 2 and clean.rain_15min_mm.iloc[-1] == 1.0


def test_counter_rebound_next_day_and_tolerance():
    df = pd.concat([rain("A", [0.0, -38.5, 0.0]),
                    rain("A", [38.5, 0.0], start=T0 + pd.Timedelta(hours=20))], ignore_index=True)
    assert rules_of(qc.clean_readings(df)[1]) == ["rain_counter_rebound", "rain_negative"]
    far = pd.concat([rain("A", [-38.5]), rain("A", [38.5], start=T0 + pd.Timedelta(hours=30))], ignore_index=True)
    assert rules_of(qc.clean_readings(far)[1]) == ["rain_negative"]               # beyond 24 h
    other = rain("A", [-38.5, 0, 12.0])                                           # real rain, not a match
    assert rules_of(qc.clean_readings(other)[1]) == ["rain_negative"]
    small = rain("A", [-1.0, 0, 1.0])                                             # tiny dips are not matched
    assert rules_of(qc.clean_readings(small)[1]) == ["rain_negative"]


def test_after_gap_latest_reading_is_kept_in_live_mode():
    df = pd.concat([rain("A", [0.0]), rain("A", [46.0], start=T0 + pd.Timedelta(hours=4))], ignore_index=True)
    clean, flags = qc.clean_readings(df)
    assert flags.empty and clean.rain_15min_mm.iloc[-1] == 46.0
    later = pd.concat([df, rain("A", [0.0], start=T0 + pd.Timedelta(hours=4, minutes=15))], ignore_index=True)
    assert rules_of(qc.clean_readings(later)[1]) == ["rain_after_gap"]            # judged once the next arrives


def test_identical_next_value_is_a_duplicated_catch_up_not_a_storm():
    df = pd.concat([rain("A", [0.0]), rain("A", [61.0, 61.0, 0.0, 0.0], start=T0 + pd.Timedelta(hours=54))],
                   ignore_index=True)
    clean, flags = qc.clean_readings(df)
    assert rules_of(flags) == ["rain_after_gap"] * 2                 # the catch-up and its identical repeat
    assert clean.rain_15min_mm.iloc[1:3].isna().all() and clean.rain_15min_mm.iloc[3] == 0.0


def test_live_loader_keeps_latest_reading(tmp_path):
    (tmp_path / "rf").mkdir()
    (tmp_path / "wl").mkdir()
    t = lambda h, m: datetime(2026, 10, 14, h, m)  # noqa: E731
    times = [t(4, 45), t(5, 0), t(8, 45)]
    pd.DataFrame({"graph_id": "G", "source_time": times, "fetched_at_local": times,
                  "rain_since_midnight_mm": [1.0, 2.0, 48.0]}).to_parquet(tmp_path / "rf" / "2026-10-14.parquet")
    wtimes = [t(8, 0), t(8, 15), t(8, 30), t(8, 45)]
    pd.DataFrame({"graph_id": "R", "source_time": wtimes, "fetched_at_local": wtimes,
                  "wl_m": [3.0, 3.1, 3.2, 6.0]}).to_parquet(tmp_path / "wl" / "2026-10-14.parquet")
    out = live.load_live_readings(tmp_path, t(0, 0))
    assert out[(out.kind == "rf") & (out.time_local == t(8, 45))].rain_15min_mm.iloc[0] == 46.0
    assert out[(out.kind == "wl") & (out.time_local == t(8, 45))].wl_m.iloc[0] == 6.0
