from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from floodready.engine import levels
from floodready.engine.types import Level, MLResult, Reason, TriggerResult
from floodready.ml import predict

T = lambda hhmm: datetime(2024, 11, 12, int(hhmm[:2]), int(hhmm[3:]))  # noqa: E731
CFG = {"p_watch": 0.35, "p_warning": 0.7, "smoothing_min": 30, "horizon_h": 2, "ml_drives_alerts": False}
RAIN = Reason("rain_1h", 61.5, "mm", "Kg. Perepat, Kapar", "61.5 mm of rain in 1 h at Kg. Perepat, Kapar",
              "Hujan 61.5 mm dalam 1 jam di Kg. Perepat, Kapar")


def rule(level):
    return TriggerResult(level=level, confidence="high", fired_by=("rule_rain",) if level else (),
                         reasons=(RAIN,) if level else (), data_time=T("09:00"), stale_stations=())


def ml(p, cfg=CFG):
    return predict.ml_result(p, "Sg. Binjai di Pekan Meru", cfg)


class FixedModel:
    """Stands in for the classifier: probability = the feature value."""
    def predict_proba(self, X):
        p = X["d_warning"].to_numpy()
        return np.column_stack([1 - p, p])


def test_ml_result_level_and_bilingual_reason():
    r = ml(0.62)
    assert r.level is Level.WATCH and r.horizon_h == 2
    assert r.reasons[0].text_en == "62% chance the river at Sg. Binjai di Pekan Meru crosses warning level within 2 h"
    assert r.reasons[0].text_ms == "62% kemungkinan paras Sg. Binjai di Pekan Meru melepasi paras amaran dalam 2 jam"
    assert ml(0.8).level is Level.WARNING and ml(0.1).level is Level.NORMAL


def test_combine_never_returns_a_level_below_the_rules():
    cfg = dict(CFG, ml_drives_alerts=True)
    assert levels.combine(rule(Level.WARNING), ml(0.05, cfg), cfg).level is Level.WARNING


def test_ml_raises_the_level_only_when_the_gate_allows_it():
    on = dict(CFG, ml_drives_alerts=True)
    raised = levels.combine(rule(Level.NORMAL), ml(0.8, on), on)
    assert raised.level is Level.WATCH and raised.fired_by == ("model",)     # two-tier: ML is capped at Watch
    kept = levels.combine(rule(Level.NORMAL), ml(0.8), CFG)
    assert kept.level is Level.NORMAL
    assert kept.reasons[0].code == "ml_probability"            # still shown


def test_combine_without_a_model_is_rules_only():
    r = rule(Level.WATCH)
    assert levels.combine(r, None, CFG) == r


def test_township_probability_is_the_max_over_its_river_stations_smoothed_over_30_min():
    feats = pd.DataFrame({
        "graph_id": ["PEKANMERU"] * 3 + ["PANDAMARAN"] * 3,
        "name": ["Sg. Binjai di Pekan Meru"] * 3 + ["P/A Pandamaran"] * 3,
        "time_local": [T("08:30"), T("08:45"), T("09:00")] * 2,
        "d_warning": [0.9, 0.2, 0.3, 0.1, 0.4, 0.5],
    })
    result = predict.township_probability(FixedModel(), ["d_warning"], feats, ["PEKANMERU", "PANDAMARAN"], T("09:00"), CFG)
    assert result.p == pytest.approx(0.9) and result.station == "Sg. Binjai di Pekan Meru"   # 08:30 still within 30 min


def test_missing_model_file_means_no_ml(tmp_path):
    assert predict.load_or_none(tmp_path / "nope.joblib") is None


def test_fold_of_matches_training_folds():
    from floodready.ml import dataset
    stamps = pd.Series(pd.to_datetime(["2024-11-12 09:00", "2025-01-05 00:00", "2025-04-01 00:00"]))
    rows = pd.DataFrame({"time_local": stamps, "wl_m": 1.0, "wl_warning_m": 4.0, "cross_2h": 0.0})
    assert dataset.fold_of(stamps).tolist() == dataset.training_rows(rows).fold.tolist()


def test_past_events_use_the_model_that_never_saw_them(tmp_path):
    from floodready.ml import dataset, train
    for name in ["trigger_v1"] + [f"trigger_v1_oof{k}" for k in range(4)]:
        train.save_model({"tag": name}, tmp_path / f"{name}.joblib", ["x"], {})
    fold = int(dataset.fold_of(pd.Series([pd.Timestamp("2024-11-12 09:00")]))[0])
    past = predict.bundle_for(tmp_path, datetime(2024, 11, 12, 9, 0), live=False)
    assert past["model"] == {"tag": f"trigger_v1_oof{fold}"} and past["out_of_sample"] is True
    live = predict.bundle_for(tmp_path, datetime(2026, 10, 15, 9, 0), live=True)
    assert live["model"] == {"tag": "trigger_v1"} and live["out_of_sample"] is False


def test_a_model_trained_on_other_features_falls_back_to_rules_not_a_crash(caplog):
    """A bundle trained on an older FEATURES list must not crash replay/live: no ML result, one warning."""
    feats = pd.DataFrame({"graph_id": ["PEKANMERU"], "name": ["Sg. Binjai"], "time_local": [T("09:00")],
                          "d_warning": [0.9]})
    with caplog.at_level("WARNING"):
        assert predict.station_probabilities(FixedModel(), ["d_warning", "n_rf_10km"], feats, ["PEKANMERU"],
                                             T("09:00"), CFG) == {}
        assert predict.township_probability(FixedModel(), ["d_warning", "n_rf_10km"], feats, ["PEKANMERU"],
                                            T("09:00"), CFG) is None
    warnings = [r for r in caplog.records if "n_rf_10km" in r.message]
    assert len(warnings) == 1   # once per model, not at every 15-min step of a replay
