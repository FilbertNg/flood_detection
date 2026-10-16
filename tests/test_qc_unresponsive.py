"""wl_unresponsive: a flat river level during heavy rain nearby is a faulty gauge; a flat level alone is base flow."""
from pathlib import Path

import numpy as np
import pandas as pd

from floodready import qc

FIXTURES = Path(__file__).parent / "fixtures" / "qc"
T0 = pd.Timestamp("2025-03-01 00:00")

STATIONS = pd.DataFrame([
    {"graph_id": "R", "kind": "wl", "lat": 3.100, "lon": 101.400},
    {"graph_id": "G", "kind": "rf", "lat": 3.130, "lon": 101.400},      # 3.3 km away
    {"graph_id": "FAR", "kind": "rf", "lat": 3.500, "lon": 101.400},    # 44 km away
])


def times(n):
    return [T0 + pd.Timedelta(minutes=15 * i) for i in range(n)]


def rain(gid, values):
    return pd.DataFrame({"graph_id": gid, "kind": "rf", "time_local": times(len(values)),
                         "rain_15min_mm": values, "wl_m": np.nan})


def level(gid, values):
    return pd.DataFrame({"graph_id": gid, "kind": "wl", "time_local": times(len(values)),
                         "rain_15min_mm": np.nan, "wl_m": values})


def storm(n=40, rain_from=4, rain_to=12, mm=10.0):
    r = np.zeros(n)
    r[rain_from:rain_to] = mm
    return r


def wl_flags(flags):
    return flags[flags.rule == "wl_unresponsive"]


def steps(f):
    return sorted(((f.time_local - T0) / pd.Timedelta(minutes=15)).astype(int))


def test_flat_level_during_heavy_rain_is_flagged_from_the_point_it_is_proven():
    df = pd.concat([rain("G", storm()), level("R", np.full(40, 1.20))], ignore_index=True)
    clean, flags = qc.clean_readings(df, stations=STATIONS)
    f = wl_flags(flags)
    assert not f.empty and set(f.graph_id) == {"R"} and (f.value == 1.20).all()
    idx = steps(f)
    assert idx[0] >= 10 and idx == list(range(idx[0], 40))       # not before 3 h of flat level, then to the end of the run
    wl = clean[clean.kind == "wl"].sort_values("time_local")
    assert wl.wl_m.isna().sum() == len(idx) and wl.wl_m.iloc[:idx[0]].notna().all()
    assert clean[clean.kind == "rf"].rain_15min_mm.sum() == storm().sum()      # rain untouched


def test_flat_level_without_rain_is_base_flow_not_a_fault():
    df = pd.concat([rain("G", np.zeros(40)), level("R", np.full(40, 1.20))], ignore_index=True)
    _, flags = qc.clean_readings(df, stations=STATIONS)
    assert wl_flags(flags).empty


def test_light_rain_below_the_total_is_not_enough():
    df = pd.concat([rain("G", storm(mm=2.0)), level("R", np.full(40, 1.20))], ignore_index=True)    # 16 mm
    _, flags = qc.clean_readings(df, stations=STATIONS)
    assert wl_flags(flags).empty


def test_responsive_river_is_not_flagged():
    rising = 1.0 + 0.05 * np.arange(40)
    df = pd.concat([rain("G", storm()), level("R", rising)], ignore_index=True)
    _, flags = qc.clean_readings(df, stations=STATIONS)
    assert wl_flags(flags).empty


def test_small_wobble_within_1_5_cm_still_counts_as_flat():
    wobble = 1.20 + 0.01 * (np.arange(40) % 2)
    df = pd.concat([rain("G", storm()), level("R", wobble)], ignore_index=True)
    _, flags = qc.clean_readings(df, stations=STATIONS)
    assert not wl_flags(flags).empty


def test_no_gauge_within_10_km_means_no_flag():
    df = pd.concat([rain("FAR", storm()), level("R", np.full(40, 1.20))], ignore_index=True)
    _, flags = qc.clean_readings(df, stations=STATIONS)
    assert wl_flags(flags).empty


def test_rule_is_skipped_without_station_coordinates():
    df = pd.concat([rain("G", storm()), level("R", np.full(40, 1.20))], ignore_index=True)
    clean, flags = qc.clean_readings(df)
    assert wl_flags(flags).empty and clean.wl_m.notna().sum() == 40
    no_coords = STATIONS.assign(lat=np.nan, lon=np.nan)
    _, flags = qc.clean_readings(df, stations=no_coords)
    assert wl_flags(flags).empty


def test_run_ends_when_the_level_moves_again():
    values = np.concatenate([np.full(30, 1.20), 1.20 + 0.1 * np.arange(1, 11)])
    df = pd.concat([rain("G", storm()), level("R", values)], ignore_index=True)
    clean, flags = qc.clean_readings(df, stations=STATIONS)
    idx = steps(wl_flags(flags))
    assert idx[-1] == 29 and idx == list(range(idx[0], 30))
    assert clean[clean.kind == "wl"].sort_values("time_local").wl_m.iloc[30:].notna().all()


def test_flags_are_causal_future_data_does_not_change_past_flags():
    r_full = storm(n=60)
    r_full[40:50] = 15.0                                       # a second storm later, over a level that stays flat
    full = pd.concat([rain("G", r_full), level("R", np.full(60, 1.20))], ignore_index=True)
    cut = T0 + pd.Timedelta(minutes=15 * 30)
    a, _ = qc.clean_readings(full[full.time_local < cut], stations=STATIONS)
    b, _ = qc.clean_readings(full, stations=STATIONS)
    b = b[b.time_local < cut]
    key = ["kind", "graph_id", "time_local"]
    pd.testing.assert_frame_equal(a.sort_values(key).reset_index(drop=True), b.sort_values(key).reset_index(drop=True))
    # rain that only arrives later cannot change earlier readings
    no_late = full.copy()
    no_late.loc[(no_late.kind == "rf") & (no_late.time_local >= T0 + pd.Timedelta(minutes=15 * 20)), "rain_15min_mm"] = 0.0
    c, _ = qc.clean_readings(no_late, stations=STATIONS)
    d, _ = qc.clean_readings(full, stations=STATIONS)
    early = lambda x: x[(x.kind == "wl") & (x.time_local < T0 + pd.Timedelta(minutes=15 * 20))].sort_values("time_local").wl_m.isna().tolist()
    assert early(c) == early(d)


def test_12_nov_2024_26558_is_flagged_and_pekan_meru_is_not():
    storm_df = pd.read_parquet(FIXTURES / "storm_20241112.parquet")
    stations = pd.read_parquet(FIXTURES / "stations_storm.parquet")
    clean, flags = qc.clean_readings(storm_df, stations=stations)
    f = wl_flags(flags)
    assert set(f.graph_id) == {"26558"} and f.value.round(2).isin([-0.78, -0.79]).all() and len(f) >= 5
    assert f.time_local.min() >= pd.Timestamp("2024-11-12 09:00")        # needs 4.5 h of flat level and rain 90 min earlier
    assert set(flags.rule) == {"wl_unresponsive"}
    pm = clean[(clean.graph_id == "PEKANMERU") & (clean.kind == "wl")]
    assert pm.wl_m.notna().all() and pm.wl_m.max() > 4.2
    others = clean[clean.graph_id != "26558"]
    pd.testing.assert_frame_equal(others.reset_index(drop=True), storm_df[storm_df.graph_id != "26558"].reset_index(drop=True))
