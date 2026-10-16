"""Training for the ML trigger (build plan task ML2).

HistGradientBoostingClassifier (handles missing readings natively), trained with
time-blocked folds; probabilities used for evaluation are always out-of-fold.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression

MODEL_PARAMS = {"max_iter": 300, "learning_rate": 0.05, "max_leaf_nodes": 31, "l2_regularization": 1.0,
                "class_weight": "balanced", "random_state": 0}


def make_model(**overrides) -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(**{**MODEL_PARAMS, **overrides})


class CalibratedModel:
    """A fitted base classifier plus an isotonic map from its raw score to a calibrated probability.

    The bundle's `model` is one of these, so `predict.py` keeps calling `model.predict_proba(X)[:, 1]` and gets
    a probability that means what it says. With `calibrator=None` it passes the base probability through.
    Plain module-level class so joblib can pickle it."""

    classes_ = np.array([0.0, 1.0])

    def __init__(self, base, calibrator=None):
        self.base, self.calibrator = base, calibrator

    def predict_proba(self, X) -> np.ndarray:
        p = self.base.predict_proba(X)[:, 1]
        if self.calibrator is not None:
            p = np.clip(self.calibrator.predict(p), 0.0, 1.0)
        return np.column_stack([1.0 - p, p])

    def without_calibration(self) -> "CalibratedModel":
        return CalibratedModel(self.base, None)


def _isotonic(raw, y) -> IsotonicRegression:
    return IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip").fit(raw, y)


class AverageModel:
    """Mean of several fitted classifiers' probabilities (the models the isotonic map was fitted on)."""

    def __init__(self, models):
        self.models = list(models)

    def predict_proba(self, X) -> np.ndarray:
        p = np.mean([m.predict_proba(X)[:, 1] for m in self.models], axis=0)
        return np.column_stack([1.0 - p, p])


def _fit_ensemble(X, y, fold, folds, overrides):
    """One model per fold j in `folds`, trained on the other folds; returns (models, oof) where the raw
    score of every row of fold j comes from the model that did not train on j."""
    models, oof = [], np.full(len(y), np.nan)
    for j in folds:
        fit = np.isin(fold, [f for f in folds if f != j])
        m = make_model(**overrides).fit(X[fit], y[fit])
        models.append(m)
        oof[fold == j] = m.predict_proba(X[fold == j])[:, 1]
    return models, oof


def cross_val_calibrated(rows: pd.DataFrame, features: list[str], label: str, class_weight: str | None = None,
                         fold_col: str = "fold", **model_overrides) -> dict:
    """Out-of-fold probabilities with calibration fitted out-of-sample and on the scale it is applied to.

    For each outer fold k (the test fold), T = the other folds:
      1. One inner model per fold j in T, trained on T minus j; each scores its held-out fold j.
      2. An isotonic map raw score -> label is fitted on those inner scores (T only, never fold k).
      3. The fold model = the AVERAGE of the inner models + that map. It scores fold k.
    The shipped model uses the same recipe over all folds: the average of the per-fold base models (each trained
    on all folds but one) with the map fitted on their out-of-fold scores. Model and map always come from the
    same models. (The map is fitted on single-model scores and applied to their average, which is slightly
    smoother; that is the price of keeping every fitted score out-of-sample.)
    Returns oof_raw / oof_cal (numpy, aligned to `rows`), fold_models {fold: CalibratedModel},
    final_model, and the params used."""
    overrides = {"class_weight": class_weight, **model_overrides}
    y = rows[label].to_numpy()
    fold = rows[fold_col].to_numpy()
    X = rows[features]
    folds = sorted(int(f) for f in np.unique(fold))
    oof_raw, oof_cal = np.full(len(rows), np.nan), np.full(len(rows), np.nan)
    fold_models: dict[int, CalibratedModel] = {}
    for k in folds:
        t = fold != k
        models, inner = _fit_ensemble(X[t], y[t], fold[t], [f for f in folds if f != k], overrides)
        model = CalibratedModel(AverageModel(models), _isotonic(inner, y[t]))
        fold_models[k] = model
        oof_raw[fold == k] = model.without_calibration().predict_proba(X[fold == k])[:, 1]
        oof_cal[fold == k] = model.predict_proba(X[fold == k])[:, 1]
    models, full = _fit_ensemble(X, y, fold, folds, overrides)
    final = CalibratedModel(AverageModel(models), _isotonic(full, y))
    return {"oof_raw": oof_raw, "oof_cal": oof_cal, "fold_models": fold_models, "final_model": final,
            "params": {**MODEL_PARAMS, **overrides}}


def pick_calibration(stats: dict[str, dict], max_pr_auc_loss: float = 0.01) -> str:
    """Lowest out-of-fold Brier score among options whose PR-AUC is within `max_pr_auc_loss` of the best."""
    best_pr = max(s["pr_auc"] for s in stats.values())
    eligible = {k: s for k, s in stats.items() if s["pr_auc"] >= best_pr - max_pr_auc_loss}
    return min(eligible, key=lambda k: eligible[k]["brier"])


def cross_val_proba(rows: pd.DataFrame, features: list[str], label: str, fold_col: str = "fold",
                    return_fold_models: bool = False, models_out: dict | None = None):
    """Out-of-fold probabilities: each fold is predicted by a model that never saw it.
    Pass a dict as `models_out` to keep each fold's model (used to replay past events out-of-sample)."""
    proba = pd.Series(index=rows.index, dtype=float)
    used = {}
    for fold in sorted(rows[fold_col].unique()):
        test = rows[fold_col] == fold
        model = make_model().fit(rows.loc[~test, features], rows.loc[~test, label])
        proba[test] = model.predict_proba(rows.loc[test, features])[:, 1]
        used[fold] = set(rows.loc[~test, fold_col].unique())
        if models_out is not None:
            models_out[int(fold)] = model
    return (proba, used) if return_fold_models else proba


def fit_final(rows: pd.DataFrame, features: list[str], label: str) -> HistGradientBoostingClassifier:
    return make_model().fit(rows[features], rows[label])


def smooth(probs: pd.DataFrame, minutes: int = 30) -> pd.DataFrame:
    """p_smooth = max of p over the last `minutes` (inclusive) per station."""
    out = []
    for _, g in probs.sort_values("time_local").groupby("graph_id", sort=False):
        s = g.set_index("time_local")["p"].rolling(f"{minutes}min", closed="both").max()
        out.append(g.assign(p_smooth=s.to_numpy()))
    return pd.concat(out).sort_index()


def save_model(model, path: Path, features: list[str], card: dict, params: dict | None = None) -> None:
    """Model artifact + a JSON sidecar (features, params) + a human-readable model card."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    params = params or MODEL_PARAMS
    joblib.dump({"model": model, "features": features, "params": params,
                 "trained_at": datetime.now().isoformat(timespec="seconds")}, path)
    path.with_suffix(".json").write_text(json.dumps({"features": features, "params": params, **card},
                                                    indent=2, default=str), encoding="utf-8")


def load_model(path: Path) -> dict:
    return joblib.load(path)
