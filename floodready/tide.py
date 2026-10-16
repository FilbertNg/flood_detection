"""Hourly tide for Port Klang (build plan task G3).

Source: Open-Meteo Marine `sea_level_height_msl` at an offshore point near
Port Klang (model data; the docs warn coastal accuracy is limited). Cross-check
against JUPEM tide tables before quoting tide in public material.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
PORT_KLANG_OFFSHORE = (2.95, 101.25)

# Tidal constituents: angular speed in degrees per hour (standard values).
CONSTITUENTS_DEG_PER_H = {
    "M2": 28.9841042, "S2": 30.0, "N2": 28.4397295, "K2": 30.0821373,
    "K1": 15.0410686, "O1": 13.9430356, "P1": 14.9589314, "Q1": 13.3986609,
    "M4": 57.9682084, "MS4": 58.9841042,
}
MAX_HOURS_TO_HIGH = 7.0   # beyond this the "nearest high" is not real (a gap): report NaN
_EPOCH =pd.Timestamp("2000-01-01")


def marine_params(start: str, end: str, lat: float = PORT_KLANG_OFFSHORE[0], lon: float = PORT_KLANG_OFFSHORE[1]) -> dict:
    return {"latitude": lat, "longitude": lon, "hourly": "sea_level_height_msl", "start_date": start,
            "end_date": end, "timezone": "Asia/Kuala_Lumpur", "cell_selection": "sea"}


def series_from_marine(payload: dict) -> pd.Series:
    hourly = payload["hourly"]
    values = [np.nan if v is None else float(v) for v in hourly["sea_level_height_msl"]]
    return pd.Series(values, index=pd.to_datetime(hourly["time"]), name="tide_height_m")


def _design_matrix(index: pd.DatetimeIndex) -> np.ndarray:
    hours = np.asarray((index - _EPOCH) / pd.Timedelta(hours=1), dtype=float)
    cols = [np.ones_like(hours)]
    for speed in CONSTITUENTS_DEG_PER_H.values():
        angle = np.radians(speed) * hours
        cols += [np.cos(angle), np.sin(angle)]
    return np.column_stack(cols)


@dataclass(frozen=True)
class HarmonicFit:
    """Mean + one cos/sin pair per constituent, fitted by least squares."""
    coefficients: np.ndarray
    n_samples: int

    def predict(self, index: pd.DatetimeIndex) -> pd.Series:
        return pd.Series(_design_matrix(index) @ self.coefficients, index=index, name="tide_height_m")

    def amplitudes(self) -> dict[str, float]:
        c = self.coefficients[1:].reshape(-1, 2)
        return dict(zip(CONSTITUENTS_DEG_PER_H, np.hypot(c[:, 0], c[:, 1]).tolist()))


def fit_harmonics(series: pd.Series) -> HarmonicFit:
    """Least-squares harmonic fit to the non-missing hours of `series`."""
    data = series.dropna()
    if len(data) < 2 * len(CONSTITUENTS_DEG_PER_H) + 1:
        raise ValueError("too few tide samples for a harmonic fit")
    coef, *_ = np.linalg.lstsq(_design_matrix(data.index), data.to_numpy(float), rcond=None)
    return HarmonicFit(coefficients=coef, n_samples=len(data))


def fill_gaps(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Fill missing hours (NaN or absent) with the harmonic fit. Returns (filled series, bool mask of filled hours).
    Hours with data are never changed."""
    full = series.reindex(pd.date_range(series.index.min(), series.index.max(), freq="h"))
    missing = full.isna()
    if missing.any():
        fit = fit_harmonics(series)
        full[missing] = fit.predict(full.index[missing])
    return full.rename("tide_height_m"), missing.rename("tide_filled")


def holdout_validation(series: pd.Series, start: str | pd.Timestamp, days: int = 10) -> dict:
    """Fit without the window [start, start + days) and compare the prediction with the series there.

    Returns RMSE (m), bias (m) and the high-water timing error: each observed high tide in the window
    is matched with the nearest predicted high within 3 h (hours, signed predicted - observed)."""
    start = pd.Timestamp(start)
    end = start + pd.Timedelta(days=days)
    window = series[(series.index >= start) & (series.index < end)].dropna()
    train = series.drop(window.index)
    pred = fit_harmonics(train).predict(window.index)
    err = pred - window
    obs_h, pred_h = high_tide_times(window), high_tide_times(pred)
    lags = []
    for t in obs_h:
        d = (pred_h - t) / pd.Timedelta(hours=1)
        d = d[np.abs(d) <= 3]
        if len(d):
            lags.append(float(d[np.argmin(np.abs(d))]))
    lags = np.array(lags)
    return {"start": start, "days": days, "n_hours": len(window), "rmse_m": float(np.sqrt((err ** 2).mean())),
            "bias_m": float(err.mean()), "series_std_m": float(window.std()),
            "n_highs": len(obs_h), "n_highs_matched": len(lags),
            "timing_mean_abs_h": float(np.abs(lags).mean()) if len(lags) else float("nan"),
            "timing_max_abs_h": float(np.abs(lags).max()) if len(lags) else float("nan")}


def high_tide_times(series: pd.Series) -> pd.DatetimeIndex:
    """Local maxima: higher than both neighbours (first of equal pairs)."""
    s = series.interpolate(limit=2)
    is_high = (s > s.shift(1)) & (s >= s.shift(-1))
    return s.index[is_high.fillna(False).to_numpy()]


def tide_features(series: pd.Series, filled: pd.Series | None = None) -> pd.DataFrame:
    """tide_height_m, signed hours to the nearest high tide (+ = coming, - = past) and `tide_filled`
    (True where the hour came from the harmonic fit, `filled` aligned to `series`; all False if omitted).

    Compute this on a gap-filled series (`fill_gaps`): the nearest high tide is then always within
    about half a tidal cycle. Where no high tide is found, hours_to_high_tide is NaN."""
    highs = high_tide_times(series).to_numpy()
    times = series.index.to_numpy()
    nearest = np.full(len(times), np.nan)
    if len(highs):
        pos = np.searchsorted(highs, times)
        nxt = highs[np.minimum(pos, len(highs) - 1)]
        prv = highs[np.maximum(pos - 1, 0)]
        to_next = (nxt - times) / np.timedelta64(1, "h")
        to_prev = (prv - times) / np.timedelta64(1, "h")
        to_next = np.where(to_next < 0, np.inf, to_next)
        to_prev = np.where(to_prev > 0, -np.inf, to_prev)
        nearest = np.where(to_next <= -to_prev, to_next, to_prev)
        nearest = np.where(np.isfinite(nearest) & (np.abs(nearest) <= MAX_HOURS_TO_HIGH), nearest, np.nan)
    return pd.DataFrame({"time_local": series.index, "tide_height_m": series.to_numpy(),
                         "hours_to_high_tide": nearest,
                         "tide_filled": (filled.reindex(series.index, fill_value=False).to_numpy(bool)
                                         if filled is not None else np.zeros(len(series), bool))})
