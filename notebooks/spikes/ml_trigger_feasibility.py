"""ML trigger feasibility spike (14 Oct 2026). Exploration code, not production.

Question: can ML on JPS station data tell, ahead of time, that Sg. Binjai
(Pekan Meru, BBR's river) will cross its warning level (4.0 m), and does it
beat the station rain rules? The labels come from the river data itself.

Run from the repo root after the JPS history archive has these stations:
  python -X utf8 notebooks/spikes/ml_trigger_feasibility.py
Results are written up in docs/ml-feasibility.md.
"""
import glob
import gzip
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

HIST = Path("data/raw/jps_hist")
TARGET = "PEKANMERU"  # Sg. Binjai di Pekan Meru: normal 2.8 / alert 3.8 / warning 4.0 / danger 4.2 m
RAIN = ["PEKANMERU", "26558", "KGRANTAUPANJANG", "TELOKGONG", "PANDAMARAN",
        "JLNBENTENGKAPAR", "SELATMUARA", "SMKRAJALUMU", "KGDELEK", "26038"]
ALERT, WARNING = 3.80, 4.00
FOLD_SPLIT = "2025-04-01"  # fold A (contains 12 Nov 2024) = before; fold B = after
_EMPTY = re.compile(r":\s*([,}])")


def rain_series(graph_id: str) -> pd.Series:
    """15-min rain from cached raw chunks: c15min at quarter hours (see Data Spec)."""
    values = {}
    for path in sorted(glob.glob(str(HIST / "raw" / "rf" / graph_id / "*.json.gz"))):
        text = gzip.open(path, "rt", encoding="utf-8").read()
        if "No result" in text:
            continue
        for v in json.loads(_EMPTY.sub(r":null\1", text[text.find("{"):]))["values"]:
            t = pd.to_datetime(v["dt"], format="%d/%m/%Y %H:%M")
            if t.minute % 15 == 0:
                x = v.get("c15min")
                values[t] = np.nan if x in (None, -9999, "-9999") else float(x)
    return pd.Series(values, name=graph_id).sort_index()


def load():
    wl = pd.read_parquet(HIST / "wl" / f"{TARGET}.parquet").set_index("time_local")["wl_m"].sort_index()
    idx = pd.date_range("2024-04-01", wl.index.max(), freq="15min")
    wl = wl[~wl.index.duplicated()].reindex(idx)
    rain = pd.concat([rain_series(g) for g in RAIN], axis=1)
    return wl, rain[~rain.index.duplicated()].reindex(idx), idx


def features(wl, rain, idx):
    X = pd.DataFrame(index=idx)
    for lag in [0, 1, 2, 4, 8]:
        X[f"wl_lag{lag}"] = wl.shift(lag)
    X["dwl_15"] = wl - wl.shift(1)
    X["dwl_60"] = wl - wl.shift(4)
    r0 = rain.fillna(0)
    for name, n in [("1h", 4), ("2h", 8), ("3h", 12), ("6h", 24), ("24h", 96)]:
        s = r0.rolling(n, min_periods=1).sum()
        X[f"rain_max_{name}"] = s.max(axis=1)
        X[f"rain_mean_{name}"] = s.mean(axis=1)
        X[f"rain_perepat_{name}"] = s["26558"]
    X["hour"] = idx.hour + idx.minute / 60
    X["month"] = idx.month
    return X


def two_fold(model_factory, X, y, fit_kwargs=None, predict=lambda m, x: m.predict(x)):
    out = pd.Series(index=X.index, dtype=float)
    fold_a = X.index < FOLD_SPLIT
    for test in (fold_a, ~fold_a):
        model = model_factory()
        model.fit(X[~test], y[~test])
        out[test] = predict(model, X[test])
    return out


def regression_report(wl, X):
    for steps, label in [(4, "1h"), (8, "2h")]:
        future = wl.shift(-steps)
        data = X.assign(y=future - wl, now=wl, future=future).dropna(subset=["y", "now"])
        feats = data.drop(columns=["y", "now", "future"])
        pred = data.now + two_fold(lambda: HistGradientBoostingRegressor(
            max_iter=400, learning_rate=0.05, l2_regularization=1.0, random_state=0), feats, data.y)
        err_m, err_p = (pred - data.future).abs(), (data.now - data.future).abs()
        rising = (data.future - data.now) >= 0.3
        print(f"[{label}] MAE rising ≥0.3 m: model {err_m[rising].mean():.3f} vs persistence {err_p[rising].mean():.3f} m (n={rising.sum()}); "
              f"MAE ≥ alert: model {err_m[data.future >= ALERT].mean():.3f} vs {err_p[data.future >= ALERT].mean():.3f} m")


def event_report(wl, rain, X):
    horizon = 8  # 2 h
    future_max = pd.concat([wl.shift(-k) for k in range(1, horizon + 1)], axis=1).max(axis=1)
    y = ((wl < WARNING) & (future_max >= WARNING)).astype(float)
    y[wl.isna() | future_max.isna()] = np.nan
    data = X.assign(y=y).dropna(subset=["y"])
    data = data[data.wl_lag0 < WARNING]
    feats = data.drop(columns=["y"])
    proba = two_fold(lambda: HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.05, l2_regularization=1.0, class_weight="balanced", random_state=0),
        feats, data.y, predict=lambda m, x: m.predict_proba(x)[:, 1])

    r0 = rain.fillna(0)
    s1 = r0.rolling(4, min_periods=1).sum().max(axis=1).reindex(data.index)
    s24 = pd.concat([r0.rolling(n, min_periods=1).sum().max(axis=1) for n in (8, 12, 16)], axis=1).max(axis=1).reindex(data.index)
    above = wl >= WARNING
    crossings = wl.index[(above & ~above.shift(1, fill_value=False)).values]
    months = (wl.index[-1] - wl.index[0]).days / 30.4

    def score(name, fired):
        fired = fired.reindex(wl.index, fill_value=False)
        leads = []
        for t in crossings:
            window = fired[t - pd.Timedelta("3h"): t - pd.Timedelta("15min")]
            if window.any():
                leads.append((t - window[window].index[0]).total_seconds() / 60)
        starts = fired.index[(fired & ~fired.shift(1, fill_value=False)).values]
        false = sum(1 for s in starts if not ((crossings > s) & (crossings <= s + pd.Timedelta("3h"))).any())
        lead = f"{np.median(leads):.0f} min" if leads else "-"
        print(f"{name:28s} detected {len(leads):2d}/{len(crossings)}  median lead {lead:>7s}  false alarms {false/months:.1f}/month")

    print(f"\nWill Sg Binjai cross 4.0 m within 2 h? {len(crossings)} crossings, out-of-sample")
    score("Rule Watch (rain)", (s1 >= 31) | (s24 >= 40))
    score("Rule Warning (rain)", (s1 > 60) | (s24 >= 60))
    for thr in (0.3, 0.5, 0.7):
        score(f"ML classifier p ≥ {thr}", proba >= thr)
    print("12 Nov 2024 ML p(cross within 2 h):",
          {t: round(float(proba.get(pd.Timestamp(f"2024-11-12 {t}"), np.nan)), 2) for t in ["08:15", "08:30", "08:45", "09:00", "09:15"]})


if __name__ == "__main__":
    wl, rain, idx = load()
    above = wl >= WARNING
    print(f"WL coverage {wl.notna().mean():.1%}, {len(idx):,} quarter hours; "
          f"{int((above & ~above.shift(1, fill_value=False)).sum())} warning crossings")
    X = features(wl, rain, idx)
    regression_report(wl, X)
    event_report(wl, rain, X)
