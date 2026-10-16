"""rain_monthly_implausible: a gauge whose rolling 30-day total is far above its neighbours' is a malfunction.
The series here are synthetic (the real gauge 26405 is not in the archive yet); they only exercise the rule."""
import numpy as np
import pandas as pd

from floodready import qc

T0 = pd.Timestamp("2024-04-01 00:00")
N = 60 * 96                                           # 60 days
STATIONS = pd.DataFrame([
    {"graph_id": "BAD", "kind": "rf", "lat": 3.100, "lon": 101.400},
    {"graph_id": "N1", "kind": "rf", "lat": 3.130, "lon": 101.400},     # 3.3 km
    {"graph_id": "N2", "kind": "rf", "lat": 3.100, "lon": 101.450},     # 5.5 km
    {"graph_id": "N3", "kind": "rf", "lat": 3.140, "lon": 101.440},     # 6.4 km
    {"graph_id": "FAR", "kind": "rf", "lat": 3.500, "lon": 101.400},    # 44 km
])


def series(gid, per_step, n=N):
    t = [T0 + pd.Timedelta(minutes=15 * i) for i in range(n)]
    return pd.DataFrame({"graph_id": gid, "kind": "rf", "time_local": t, "rain_15min_mm": per_step, "wl_m": np.nan})


def monthly(flags):
    return flags[flags.rule == "rain_monthly_implausible"]


def neighbours(per_step, ids=("N1", "N2", "N3")):
    return [series(g, np.full(N, per_step)) for g in ids]


def test_gauge_far_above_its_neighbours_is_flagged_causally_and_blanked():
    bad = np.full(N, 0.1)
    bad[30 * 96:] = 0.8                               # 2,304 mm in 30 days from day 30 on, neighbours ~ 288 mm
    df = pd.concat([series("BAD", bad)] + neighbours(0.1), ignore_index=True)
    clean, flags = qc.clean_readings(df, stations=STATIONS)
    f = monthly(flags)
    assert set(f.graph_id) == {"BAD"} and len(f) > 1000
    assert f.time_local.min() > T0 + pd.Timedelta(days=30)             # not before the total passes the limit
    b = clean[clean.graph_id == "BAD"]
    assert b.rain_15min_mm.isna().sum() == len(f)
    assert clean[clean.graph_id != "BAD"].rain_15min_mm.notna().all()
    cut = T0 + pd.Timedelta(days=45)                                   # causal: later data changes nothing before the cut
    a, _ = qc.clean_readings(df[df.time_local < cut], stations=STATIONS)
    key = ["kind", "graph_id", "time_local"]
    pd.testing.assert_frame_equal(a.sort_values(key).reset_index(drop=True),
                                  clean[clean.time_local < cut].sort_values(key).reset_index(drop=True))


def test_wet_month_everywhere_is_not_flagged():
    df = pd.concat([series(g, np.full(N, 0.8)) for g in ("BAD", "N1", "N2", "N3")], ignore_index=True)   # 2,304 mm at every gauge
    assert monthly(qc.clean_readings(df, stations=STATIONS)[1]).empty


def test_heavy_but_plausible_gauge_is_not_flagged():
    heavy = np.full(N, 0.1)
    heavy[:30 * 96] = 0.3                             # 864 mm, above the 600 mm floor
    neigh = np.full(N, 0.1)
    neigh[:30 * 96] = 0.105                           # about 302 mm: ratio 2.86, under 3
    df = pd.concat([series("BAD", heavy)] + [series(g, neigh) for g in ("N1", "N2", "N3")], ignore_index=True)
    assert monthly(qc.clean_readings(df, stations=STATIONS)[1]).empty


def test_below_the_absolute_floor_is_not_flagged():
    df = pd.concat([series("BAD", np.full(N, 0.15))] + neighbours(0.005), ignore_index=True)     # 432 mm vs 14 mm
    assert monthly(qc.clean_readings(df, stations=STATIONS)[1]).empty


def test_needs_two_neighbours_with_data_within_10_km():
    bad = np.full(N, 0.8)
    one = pd.concat([series("BAD", bad)] + neighbours(0.1, ("N1",)), ignore_index=True)
    assert monthly(qc.clean_readings(one, stations=STATIONS)[1]).empty
    far = pd.concat([series("BAD", bad)] + neighbours(0.1, ("N1", "FAR")), ignore_index=True)
    assert monthly(qc.clean_readings(far, stations=STATIONS)[1]).empty
    two = pd.concat([series("BAD", bad)] + neighbours(0.1, ("N1", "N2")), ignore_index=True)
    assert not monthly(qc.clean_readings(two, stations=STATIONS)[1]).empty


def test_skipped_without_station_coordinates():
    df = pd.concat([series("BAD", np.full(N, 0.8))] + neighbours(0.1), ignore_index=True)
    assert monthly(qc.clean_readings(df)[1]).empty


def test_neighbour_without_data_in_the_window_is_not_a_zero():
    df = pd.concat([series("BAD", np.full(N, 0.8)), series("N1", np.full(N, 0.7)),
                    series("N2", np.full(N, np.nan)), series("N3", np.full(N, np.nan))], ignore_index=True)
    assert monthly(qc.clean_readings(df, stations=STATIONS)[1]).empty       # one real neighbour only; empty ones are not zeros


def test_readings_already_removed_by_earlier_rules_do_not_count():
    bad = np.full(N, 0.19)                            # 547 mm in 30 days: under the 600 mm floor on its own
    bad[100] = 250.0                                  # rain_implausible: removed first, must not push the 30-day total over it
    df = pd.concat([series("BAD", bad)] + neighbours(0.02), ignore_index=True)
    _, flags = qc.clean_readings(df, stations=STATIONS)
    assert monthly(flags).empty and (flags.rule == "rain_implausible").sum() == 1


def test_flagging_stops_within_a_week_of_the_fault_ending_not_after_30_days():
    bad = np.full(N, 0.1)
    bad[30 * 96: 45 * 96] = 0.8                       # a 15-day fault, then normal again
    df = pd.concat([series("BAD", bad)] + neighbours(0.1), ignore_index=True)
    f = monthly(qc.clean_readings(df, stations=STATIONS)[1])
    assert len(f) > 500 and f.time_local.max() <= T0 + pd.Timedelta(days=45 + 7)
    assert qc.RAIN_MONTH_SHORT_STEPS == 7 * 96


def test_zero_readings_are_kept_while_flagged():
    bad = np.full(N, 0.8)
    bad[::4] = 0.0
    df = pd.concat([series("BAD", bad)] + neighbours(0.1), ignore_index=True)
    clean, flags = qc.clean_readings(df, stations=STATIONS)
    f = monthly(flags)
    assert len(f) > 500 and (f.value > 0).all()
    late = clean[clean.graph_id == "BAD"].sort_values("time_local").iloc[50 * 96:]
    assert late.rain_15min_mm.isna().sum() > 0 and late.rain_15min_mm.eq(0.0).sum() == len(late) // 4


def test_neighbours_need_80_percent_coverage_and_are_never_zero_filled():
    bad = np.full(N, 0.8)
    for missing_every, expect_flag in ((4, False), (5, True)):                # 75 % coverage: not counted, 80 %: counted
        nb = []
        for g in ("N1", "N2"):
            v = np.full(N, 0.1)
            v[::missing_every] = np.nan
            nb.append(series(g, v))
        got = not monthly(qc.clean_readings(pd.concat([series("BAD", bad)] + nb, ignore_index=True), stations=STATIONS)[1]).empty
        assert got == expect_flag


def test_gauge_without_coordinates_is_compared_with_its_district():
    st = STATIONS.assign(district="KL")
    st.loc[st.graph_id == "BAD", ["lat", "lon"]] = np.nan                   # like 26405: no coordinates in the lookup
    df = pd.concat([series("BAD", np.full(N, 0.8))] + neighbours(0.1), ignore_index=True)
    assert not monthly(qc.clean_readings(df, stations=st)[1]).empty
    other = st.assign(district=np.where(st.graph_id == "BAD", "KL", "SELANGOR"))
    assert monthly(qc.clean_readings(df, stations=other)[1]).empty          # nobody to compare with
    assert monthly(qc.clean_readings(df, stations=STATIONS.assign(lat=np.where(STATIONS.graph_id == "BAD", np.nan, STATIONS.lat)))[1]).empty   # no district column: skipped
