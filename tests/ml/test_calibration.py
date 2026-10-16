import io

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression

from floodready.ml import evaluate, train


def fake_rows(n=3000, seed=0, rare=0.05):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    y = (x + rng.normal(scale=0.8, size=n) > np.quantile(x, 1 - rare) + 0.3).astype(float)
    return pd.DataFrame({"f1": x, "f2": rng.normal(size=n), "fold": np.arange(n) % 4, "cross_2h": y})


def test_wrapper_is_picklable_monotone_and_bounded():
    rows = fake_rows()
    base = HistGradientBoostingClassifier(max_iter=30, random_state=0).fit(rows[["f1", "f2"]], rows.cross_2h)
    raw = base.predict_proba(rows[["f1", "f2"]])[:, 1]
    iso = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip").fit(raw, rows.cross_2h)
    model = train.CalibratedModel(base, iso)
    buf = io.BytesIO()
    joblib.dump(model, buf)
    buf.seek(0)
    loaded = joblib.load(buf)
    proba = loaded.predict_proba(rows[["f1", "f2"]])
    assert proba.shape == (len(rows), 2) and np.allclose(proba.sum(axis=1), 1)
    assert proba.min() >= 0 and proba.max() <= 1
    order = np.argsort(raw)
    assert (np.diff(proba[order, 1]) >= -1e-12).all()  # monotone in the raw score
    assert list(loaded.classes_) == [0.0, 1.0]


def test_wrapper_without_calibrator_passes_the_base_probability_through():
    rows = fake_rows()
    base = HistGradientBoostingClassifier(max_iter=10, random_state=0).fit(rows[["f1", "f2"]], rows.cross_2h)
    m = train.CalibratedModel(base, None)
    assert np.allclose(m.predict_proba(rows[["f1", "f2"]]), base.predict_proba(rows[["f1", "f2"]]))


def test_calibrated_oof_predictions_for_a_fold_do_not_depend_on_that_folds_labels():
    rows = fake_rows(n=2400)
    feats = ["f1", "f2"]
    out1 = train.cross_val_calibrated(rows, feats, "cross_2h", class_weight="balanced", max_iter=20)
    scrambled = rows.copy()
    test = scrambled.fold == 2
    scrambled.loc[test, "cross_2h"] = 1.0 - scrambled.loc[test, "cross_2h"]
    out2 = train.cross_val_calibrated(scrambled, feats, "cross_2h", class_weight="balanced", max_iter=20)
    t = rows.fold == 2
    assert np.allclose(out1["oof_cal"][t], out2["oof_cal"][t])
    assert np.allclose(out1["oof_raw"][t], out2["oof_raw"][t])
    assert not np.allclose(out1["oof_cal"][~t], out2["oof_cal"][~t])  # the other folds do learn from it


def test_isotonic_on_inner_oof_fixes_an_overconfident_balanced_model():
    rows = fake_rows(n=8000, rare=0.03)
    feats = ["f1", "f2"]
    out = train.cross_val_calibrated(rows, feats, "cross_2h", class_weight="balanced", max_iter=40)
    y = rows.cross_2h.to_numpy()
    assert evaluate.brier(out["oof_cal"], y) < evaluate.brier(out["oof_raw"], y)
    assert evaluate.ece(out["oof_cal"], y) < evaluate.ece(out["oof_raw"], y)
    assert set(out["fold_models"]) == {0, 1, 2, 3}
    p = out["fold_models"][1].predict_proba(rows[feats])[:, 1]
    assert p.min() >= 0 and p.max() <= 1
    assert out["final_model"].predict_proba(rows[feats]).shape == (len(rows), 2)


def test_pick_calibration_best_brier_with_pr_auc_not_worse_than_001():
    stats = {"a": {"brier": 0.010, "pr_auc": 0.70}, "b": {"brier": 0.008, "pr_auc": 0.70},
             "c": {"brier": 0.007, "pr_auc": 0.68}}
    assert train.pick_calibration(stats) == "b"   # c has the best Brier but loses 0.02 PR-AUC
    stats["c"]["pr_auc"] = 0.695
    assert train.pick_calibration(stats) == "c"


def test_reliability_brier_and_ece():
    p = np.array([0.02, 0.02, 0.95, 0.95])
    y = np.array([0, 0, 1, 1])
    assert evaluate.brier(p, y) == pytest.approx(0.00145)
    assert evaluate.ece(p, y) == pytest.approx(0.035)
    t = evaluate.reliability_table(p, y)
    assert t.n.sum() == 4 and t.loc[t.n > 0, "observed"].tolist() == [0.0, 1.0]
