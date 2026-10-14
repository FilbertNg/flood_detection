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
