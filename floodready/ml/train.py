"""Training for the ML trigger (build plan task ML2).

HistGradientBoostingClassifier (handles missing readings natively), trained with
time-blocked folds; probabilities used for evaluation are always out-of-fold.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

MODEL_PARAMS = {"max_iter": 300, "learning_rate": 0.05, "max_leaf_nodes": 31, "l2_regularization": 1.0,
                "class_weight": "balanced", "random_state": 0}


def make_model() -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(**MODEL_PARAMS)


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


def save_model(model, path: Path, features: list[str], card: dict) -> None:
    """Model artifact + a JSON sidecar (features, params) + a human-readable model card."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "features": features, "params": MODEL_PARAMS,
                 "trained_at": datetime.now().isoformat(timespec="seconds")}, path)
    path.with_suffix(".json").write_text(json.dumps({"features": features, "params": MODEL_PARAMS, **card},
                                                    indent=2, default=str), encoding="utf-8")


def load_model(path: Path) -> dict:
    return joblib.load(path)
