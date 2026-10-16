import numpy as np
import pandas as pd
import pytest

from floodready.ml import evaluate, train

IDX = pd.date_range("2024-11-12 00:00", "2024-11-12 23:45", freq="15min")


def level_crossing_at(hhmm, before=3.0, after=4.2):
    return pd.Series(np.where(IDX < pd.Timestamp(f"2024-11-12 {hhmm}"), before, after), index=IDX)


def fired_between(start, end):
    return pd.Series((IDX >= pd.Timestamp(f"2024-11-12 {start}")) & (IDX <= pd.Timestamp(f"2024-11-12 {end}")), index=IDX)


def test_alarm_60_min_before_a_crossing_is_detected_with_lead_60():
    m = evaluate.event_metrics(level_crossing_at("10:00"), fired_between("09:00", "09:45"), warning=4.0)
    assert (m["crossings"], m["detected"], m["median_lead_min"], m["false_alarms"]) == (1, 1, 60.0, 0)


def test_alarm_with_no_crossing_in_the_next_3_h_is_false():
    m = evaluate.event_metrics(pd.Series(3.0, index=IDX), fired_between("14:00", "14:30"), warning=4.0)
    assert (m["crossings"], m["detected"], m["false_alarms"]) == (0, 0, 1)


def test_alarm_too_early_does_not_count_as_detection():
    m = evaluate.event_metrics(level_crossing_at("18:00"), fired_between("09:00", "09:15"), warning=4.0)
    assert m["detected"] == 0 and m["false_alarms"] == 1


def test_series_starting_above_warning_is_not_a_crossing():
    m = evaluate.event_metrics(pd.Series(4.5, index=IDX), fired_between("09:00", "09:00"), warning=4.0)
    assert m["crossings"] == 0


def test_smoothing_keeps_the_max_over_the_last_30_minutes_per_station():
    probs = pd.DataFrame({"graph_id": ["A"] * 5 + ["B"] * 2,
                          "time_local": list(IDX[:5]) + list(IDX[:2]),
                          "p": [0.1, 0.9, 0.2, 0.1, 0.1, 0.5, 0.0]})
    smoothed = train.smooth(probs, minutes=30)
    assert smoothed[smoothed.graph_id == "A"].p_smooth.tolist() == [0.1, 0.9, 0.9, 0.9, 0.2]
    assert smoothed[smoothed.graph_id == "B"].p_smooth.tolist() == [0.5, 0.5]


def test_out_of_fold_probabilities_never_come_from_a_model_trained_on_that_fold():
    rng = np.random.default_rng(0)
    n = 2000
    x = rng.normal(size=n)
    rows = pd.DataFrame({"f1": x, "f2": rng.normal(size=n), "fold": np.arange(n) % 4,
                         "cross_2h": (x + rng.normal(scale=0.3, size=n) > 1.0).astype(float)})
    oof, used = train.cross_val_proba(rows, ["f1", "f2"], "cross_2h", return_fold_models=True)
    assert len(oof) == n and oof.between(0, 1).all()
    for fold, model_folds in used.items():
        assert fold not in model_folds
    from sklearn.metrics import roc_auc_score
    assert roc_auc_score(rows.cross_2h, oof) > 0.9


GATE = {"min_extra_lead_min": 20, "max_false_alarm_ratio": 1.2}
RULE = {"detected": 23, "crossings": 50, "median_lead_min": 60.0, "false_per_station_month": 4.9}


def ml(detected, false, lead):
    return {"detected": detected, "crossings": 50, "median_lead_min": lead, "false_per_station_month": false}


def test_gate_a_more_or_equal_detection_with_no_more_false_alarms():
    assert evaluate.gate(RULE, ml(23, 4.6, 90.0), GATE) == (True, "a")


def test_gate_b_same_detection_with_20_min_more_lead_and_at_most_1_2x_false_alarms():
    assert evaluate.gate(RULE, ml(23, 5.5, 90.0), GATE) == (True, "b")
    assert evaluate.gate(RULE, ml(23, 6.0, 90.0), GATE) == (False, "")      # 6.0 > 1.2 x 4.9
    assert evaluate.gate(RULE, ml(23, 5.5, 70.0), GATE) == (False, "")      # only 10 min more lead


def test_gate_fails_when_ml_detects_less():
    assert evaluate.gate(RULE, ml(18, 2.0, 120.0), GATE) == (False, "")


def test_pick_threshold_prefers_a_passing_threshold_with_most_detections():
    candidates = [(0.3, ml(26, 8.0, 90.0)), (0.5, ml(24, 4.5, 90.0)), (0.7, ml(23, 3.0, 90.0))]
    assert evaluate.pick_threshold(candidates, RULE, GATE) == (0.5, True, "a")


def test_pick_threshold_reports_failure_but_still_returns_the_best_safe_threshold():
    candidates = [(0.3, ml(20, 8.0, 90.0)), (0.5, ml(18, 4.6, 90.0)), (0.7, ml(16, 2.6, 90.0))]
    assert evaluate.pick_threshold(candidates, RULE, GATE) == (0.5, False, "")


# ---------------------------------------------------------------- WP3: alarm precision, tidal stations, gate v2

def test_alarm_precision_is_the_share_of_alarm_episodes_followed_by_a_crossing():
    level = level_crossing_at("10:00")
    fired = fired_between("09:00", "09:45") | fired_between("14:00", "14:30") | fired_between("20:00", "20:15")
    m = evaluate.event_metrics(level, fired, warning=4.0)
    # the first alarm precedes the crossing; the other two are false (the level stays above warning afterwards)
    assert m["alarms"] == 3 and m["false_alarms"] == 2
    assert m["alarm_precision"] == pytest.approx(1 / 3)


def test_alarm_precision_is_none_without_alarms_and_pooled_sums_alarms():
    m0 = evaluate.event_metrics(pd.Series(3.0, index=IDX), pd.Series(False, index=IDX), warning=4.0)
    assert m0["alarms"] == 0 and m0["alarm_precision"] is None
    a = evaluate.event_metrics(level_crossing_at("10:00"), fired_between("09:00", "09:45"), warning=4.0)
    b = evaluate.event_metrics(pd.Series(3.0, index=IDX), fired_between("14:00", "14:30"), warning=4.0)
    p = evaluate.pooled([a, b])
    assert p["alarms"] == 2 and p["alarm_precision"] == pytest.approx(0.5)


def test_tidal_stations_separates_a_12h_tide_from_a_rain_driven_river():
    t = pd.date_range("2024-01-01", periods=96 * 20, freq="15min")
    tide = pd.Series(2.0 + np.sin(2 * np.pi * np.arange(len(t)) / (12.42 * 4)), index=t)
    rng = np.random.default_rng(1)
    storms = np.zeros(len(t))
    for s in rng.integers(0, len(t) - 200, 8):
        storms[s:s + 160] += np.exp(-np.arange(160) / 40.0)
    river = pd.Series(1.0 + storms + rng.normal(0, 0.01, len(t)), index=t)
    assert evaluate.tidal_stations({"TIDE": tide, "RIVER": river}) == {"TIDE"}


def test_tidal_stations_ignores_missing_levels_and_short_series():
    t = pd.date_range("2024-01-01", periods=10, freq="15min")
    assert evaluate.tidal_stations({"X": pd.Series(np.nan, index=t), "Y": pd.Series(1.0, index=t)}) == set()


CFG2 = {"min_extra_lead_min": 30, "max_false_alarm_ratio": 1.5, "min_fresh_crossings": 30}


def m2(detected, crossings, lead, fa):
    return {"detected": detected, "crossings": crossings, "median_lead_min": lead, "false_per_station_month": fa}


def test_gate_v2_criteria_1_and_2():
    f = m2(90, 100, 60.0, 4.0)
    assert evaluate.gate_v2(f, m2(95, 100, 90.0, 6.0), None, None, CFG2)["passed"]
    assert not evaluate.gate_v2(f, m2(95, 100, 89.0, 6.0), None, None, CFG2)["passed"]      # lead +29 min
    assert not evaluate.gate_v2(f, m2(95, 100, 120.0, 6.1), None, None, CFG2)["passed"]     # FA 1.525x
    assert not evaluate.gate_v2(f, m2(95, 100, None, 4.0), None, None, CFG2)["passed"]      # nothing detected


def test_gate_v2_fresh_stations_gate_only_with_30_or_more_crossings():
    f, good = m2(90, 100, 60.0, 4.0), m2(95, 100, 100.0, 5.0)
    r = evaluate.gate_v2(f, good, m2(28, 30, 60.0, 4.0), m2(29, 30, 70.0, 4.0), CFG2)   # fresh fails, enough crossings
    assert not r["passed"] and r["fresh_gating"]
    r = evaluate.gate_v2(f, good, m2(28, 29, 60.0, 4.0), m2(29, 29, 70.0, 4.0), CFG2)   # 29 crossings: reported only
    assert r["passed"] and not r["fresh_gating"]
    r = evaluate.gate_v2(f, good, m2(28, 30, 60.0, 4.0), m2(29, 30, 100.0, 5.0), CFG2)  # fresh passes
    assert r["passed"] and r["fresh_gating"]


def block(fold, station, floor, **tiers):
    return {"station": station, "fold": fold, "inland": True,
            "metrics": {"floor": floor, **{f"two_tier_{k}": v for k, v in tiers.items()}}}


def met(detected, fa, months=1.0, lead=60.0):
    return {"crossings": 10, "detected": detected, "leads": [lead] * detected, "median_lead_min": lead,
            "false_alarms": fa, "alarms": fa + detected, "months": months}


def test_select_theta_most_detections_within_1_5x_floor_false_alarms():
    blocks = [block(0, "A", met(8, 4), **{"0.1": met(10, 7), "0.2": met(9, 6), "0.3": met(8, 5)})]
    # floor fa = 4 -> limit 6: 0.1 (7) is too noisy, 0.2 (6) is the most sensitive within the limit
    assert evaluate.select_theta(blocks, [0.1, 0.2, 0.3], 1.5) == 0.2


def test_select_theta_falls_back_to_the_most_conservative_when_none_fit():
    blocks = [block(0, "A", met(8, 2), **{"0.1": met(10, 9), "0.2": met(9, 8)})]
    assert evaluate.select_theta(blocks, [0.1, 0.2], 1.5) == 0.2


def test_nested_thetas_never_look_at_the_outer_fold():
    # fold 3 is noisy at 0.1; folds 0-2 are clean. Fold 3's own data must not decide fold 3's threshold.
    def b(fold, noisy):
        return block(fold, "A", met(8, 4), **{"0.1": met(10, 20 if noisy else 5), "0.2": met(9, 5)})
    th = evaluate.nested_thetas([b(0, False), b(1, False), b(2, False), b(3, True)], [0.1, 0.2], 1.5)
    assert th == {0: 0.2, 1: 0.2, 2: 0.2, 3: 0.1}


def test_nested_threshold_for_a_fold_is_unchanged_by_that_folds_own_data():
    base = [block(f, "A", met(8, 4), **{"0.1": met(10, 5), "0.2": met(9, 5)}) for f in range(4)]
    changed = list(base)
    changed[3] = block(3, "A", met(8, 4), **{"0.1": met(10, 99), "0.2": met(9, 5)})
    assert evaluate.nested_thetas(base, [0.1, 0.2], 1.5)[3] == evaluate.nested_thetas(changed, [0.1, 0.2], 1.5)[3]


def test_nested_pool_uses_each_blocks_own_fold_threshold():
    blocks = [block(0, "A", met(8, 4), **{"0.1": met(10, 5), "0.2": met(9, 3)}),
              block(1, "A", met(8, 4), **{"0.1": met(7, 5), "0.2": met(6, 3)})]
    p = evaluate.nested_pool(blocks, {0: 0.1, 1: 0.2}, "two_tier")
    assert p["detected"] == 10 + 6
