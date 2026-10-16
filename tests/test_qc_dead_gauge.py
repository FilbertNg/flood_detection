"""wl_unresponsive, station-level dead-gauge state: two storms (two gauges >= 30 mm) in 30 days with no response
at the gauge while a neighbouring river station responded -> every reading below alert is flagged until the gauge
shows a real response. Synthetic series (no real data), 15-min steps."""
import numpy as np
import pandas as pd

from floodready import qc

T0 = pd.Timestamp("2025-03-01 00:00")
N = 60 * 96
ALERT = 3.5
STATIONS = pd.DataFrame([
    {"graph_id": "R", "kind": "wl", "lat": 3.100, "lon": 101.400, "wl_alert_m": ALERT, "thresholds_ok": True},
    {"graph_id": "R2", "kind": "wl", "lat": 3.200, "lon": 101.400, "wl_alert_m": ALERT, "thresholds_ok": True},    # 11 km
    {"graph_id": "FARR", "kind": "wl", "lat": 3.500, "lon": 101.400, "wl_alert_m": ALERT, "thresholds_ok": True},  # 44 km
    {"graph_id": "G", "kind": "rf", "lat": 3.130, "lon": 101.400},
    {"graph_id": "G2", "kind": "rf", "lat": 3.100, "lon": 101.450},
])


def times(n=N):
    return [T0 + pd.Timedelta(minutes=15 * i) for i in range(n)]


def rain_at(days):
    r = np.zeros(N)
    for d in days:
        r[int(d * 96): int(d * 96) + 8] = 10.0          # 80 mm in 2 h at both gauges
    return pd.concat([pd.DataFrame({"graph_id": g, "kind": "rf", "time_local": times(), "rain_15min_mm": r, "wl_m": np.nan})
                      for g in ("G", "G2")], ignore_index=True)


def river(gid, values):
    return pd.DataFrame({"graph_id": gid, "kind": "wl", "time_local": times(), "rain_15min_mm": np.nan, "wl_m": values})


def sawtooth(base=1.2):
    return base + 0.03 * ((np.arange(N) % 5) / 4)       # moves 3 cm: never "flat" (so the run rule is not what flags it), < 10 cm


def responding(days, rise=0.5, base=1.0):
    v = np.full(N, base)
    for d in days:
        s = int(d * 96)
        v[s + 4: s + 40] = base + rise * np.sin(np.pi * np.arange(36) / 36)      # a flood wave, not a plateau
    return v


def run(df, stations=STATIONS):
    clean, flags = qc.clean_readings(pd.concat(df, ignore_index=True), stations=stations)
    f = flags[(flags.rule == "wl_unresponsive") & (flags.graph_id == "R")]
    return clean, set(((pd.to_datetime(f.time_local) - T0) / pd.Timedelta(minutes=15)).astype(int)), flags


def test_constants_are_exposed_with_the_pre_stated_values():
    assert (qc.WL_DEAD_EVENTS, qc.WL_DEAD_WINDOW_DAYS, qc.WL_DEAD_NO_RESPONSE_M, qc.WL_DEAD_RESPONSE_HOURS) == (2, 30, 0.10, 8)
    assert (qc.WL_DEAD_NEIGHBOUR_KM, qc.WL_DEAD_NEIGHBOUR_RISE_M, qc.WL_DEAD_EXIT_RISE_M) == (15.0, 0.3, 0.2)


def test_two_unresponsive_storms_with_a_responding_neighbour_make_the_gauge_dead():
    storms = [3, 10]
    _, f, _ = run([rain_at(storms), river("R", sawtooth()), river("R2", responding(storms))])
    eval_t = int(10 * 96) + 32                           # the second storm's response window closes 8 h after it starts
    assert min(f) >= eval_t and max(f) == N - 1
    assert f >= set(range(eval_t + 8, N))                # then every reading is flagged, including dry days


def test_two_storms_within_48_hours_are_one_miss_not_two():
    assert qc.WL_DEAD_EVENTS_APART_H == 48
    storms = [3, 3.75]                                   # 18 h apart: the same weather system
    _, f, _ = run([rain_at(storms), river("R", sawtooth()), river("R2", responding(storms))])
    assert not f
    storms = [3, 5.5]
    _, f, _ = run([rain_at(storms), river("R", sawtooth()), river("R2", responding(storms))])
    assert f


def test_one_unresponsive_storm_is_not_enough():
    _, f, _ = run([rain_at([3]), river("R", sawtooth()), river("R2", responding([3]))])
    assert not f


def test_storms_more_than_30_days_apart_do_not_count_together():
    _, f, _ = run([rain_at([3, 40]), river("R", sawtooth()), river("R2", responding([3, 40]))])
    assert not f


def test_a_dry_catchment_gauge_is_not_dead_when_the_neighbour_did_not_respond_either():
    _, f, _ = run([rain_at([3, 10]), river("R", sawtooth()), river("R2", np.full(N, 1.0))])
    assert not f


def test_neighbour_beyond_15_km_does_not_corroborate_but_no_neighbour_at_all_does_not_block():
    storms = [3, 10]
    far_only = STATIONS[STATIONS.graph_id != "R2"]
    _, f, _ = run([rain_at(storms), river("R", sawtooth()), river("FARR", responding(storms))], far_only)
    assert f                                             # no neighbour in range with data: the gauge's own two misses decide
    _, f, _ = run([rain_at(storms), river("R", sawtooth()), river("R2", np.full(N, 1.0)), river("FARR", responding(storms))])
    assert not f                                         # the in-range neighbour is quiet, the far one is not asked


def test_a_response_in_between_resets_the_count():
    r = sawtooth()
    s = int(10 * 96)
    r[s + 4: s + 40] += 0.4                              # the gauge answers the second storm
    storms = [3, 10, 17]
    _, f, _ = run([rain_at(storms), river("R", r), river("R2", responding(storms))])
    assert not f or min(f) > int(17 * 96)                # only one unresponsive storm since the reset: not dead before the 4th
    _, f, _ = run([rain_at([3, 10, 17, 24]), river("R", r), river("R2", responding([3, 10, 17, 24]))])
    assert min(f) >= int(24 * 96)                        # storms 17 and 24 are two in a row


def test_dead_state_ends_with_a_real_response_and_the_response_is_kept():
    storms = [3, 10]
    r = sawtooth()
    r[30 * 96:] += 0.6                                   # the gauge comes back to life at day 30 (rise 0.6 m)
    clean, f, _ = run([rain_at(storms), river("R", r), river("R2", responding(storms))])
    assert max(f) < 30 * 96 + 40 and 30 * 96 + 40 not in f
    wl = clean[(clean.graph_id == "R") & (clean.kind == "wl")].sort_values("time_local")
    assert wl.wl_m.iloc[40 * 96:].notna().all()


def test_never_flags_at_or_above_alert_even_while_dead():
    storms = [3, 10]
    r = sawtooth()
    r[20 * 96: 20 * 96 + 4] = ALERT + 0.2                # a reading above alert while "dead": kept (and ends the dead state)
    clean, f, _ = run([rain_at(storms), river("R", r), river("R2", responding(storms))])
    assert not ({20 * 96, 20 * 96 + 1, 20 * 96 + 2, 20 * 96 + 3} & f)
    wl = clean[(clean.graph_id == "R") & (clean.kind == "wl")].sort_values("time_local")
    assert (wl.wl_m >= ALERT).sum() == 4


def test_untrusted_thresholds_or_missing_alert_never_enter_the_dead_state():
    storms = [3, 10]
    for st in (STATIONS.assign(thresholds_ok=STATIONS.graph_id != "R"), STATIONS.assign(wl_alert_m=np.where(STATIONS.graph_id == "R", np.nan, ALERT))):
        _, f, _ = run([rain_at(storms), river("R", sawtooth()), river("R2", responding(storms))], st)
        assert not f


def test_a_responsive_river_is_never_flagged():
    storms = [3, 10, 17]
    _, f, flags = run([rain_at(storms), river("R", responding(storms, base=1.2)), river("R2", responding(storms))])
    assert not f and flags.empty


def test_dead_state_is_causal():
    storms = [3, 10]
    df = [rain_at(storms), river("R", sawtooth()), river("R2", responding(storms))]
    full, _, _ = run(df)
    cut = T0 + pd.Timedelta(days=20)
    part, _ = qc.clean_readings(pd.concat(df, ignore_index=True).query("time_local < @cut"), stations=STATIONS)
    key = ["kind", "graph_id", "time_local"]
    pd.testing.assert_frame_equal(part.sort_values(key).reset_index(drop=True), full[full.time_local < cut].sort_values(key).reset_index(drop=True))
