"""Hourly tide for Port Klang (build plan task G3).

Source: Open-Meteo Marine `sea_level_height_msl` at an offshore point near
Port Klang (model data; the docs warn coastal accuracy is limited). Cross-check
against JUPEM tide tables before quoting tide in public material.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
PORT_KLANG_OFFSHORE = (2.95, 101.25)

# Tidal constituents: angular speed in degrees per hour (standard values).
CONSTITUENTS_DEG_PER_H = {
    "M2": 28.9841042, "S2": 30.0, "N2": 28.4397295, "K2": 30.0821373,
    "K1": 15.0410686, "O1": 13.9430356, "P1": 14.9589314, "Q1": 13.3986609,
    "M4": 57.9682084, "MS4": 58.9841042,
    "Sa": 0.0410686, "Ssa": 0.0821373,
}
# Open-Meteo's high waters are consistently EARLY against independent data (docs/tide-check.md, WP7):
# UHSLC station 140 Port Kelang gauge, 86 highs Nov 2022-Jan 2023: median -35 min (sd 10); news-relayed official
# forecasts 2024: -48 min mean; tide-forecast.com 2026: -38 min. Amplitude is ~10 % too small, but tide_height_m is
# kept as is (an anomaly feature, not a chart-datum height). High-water timing is shifted later by this many minutes.
TIDE_PHASE_SHIFT_MIN = 40.0
SUBHOURLY_STEP_MIN = 5
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


def high_water_times_subhourly(fit: HarmonicFit, start: pd.Timestamp, end: pd.Timestamp,
                               phase_shift_min: float = TIDE_PHASE_SHIFT_MIN,
                               step_min: int = SUBHOURLY_STEP_MIN) -> pd.DatetimeIndex:
    """High waters of the harmonic fit evaluated every `step_min` minutes over [start - 1 d, end + 1 d],
    shifted later by `phase_shift_min` (the fit is evaluated at t - shift). No whole-hour rounding."""
    grid = pd.date_range(pd.Timestamp(start).floor("h") - pd.Timedelta(days=1),
                         pd.Timestamp(end) + pd.Timedelta(days=1), freq=f"{step_min}min")
    pred = fit.predict(grid - pd.Timedelta(minutes=phase_shift_min))
    is_high = (pred > pred.shift(1)) & (pred >= pred.shift(-1))
    return grid[is_high.fillna(False).to_numpy()]


def hours_to_nearest_high(index: pd.DatetimeIndex, highs) -> np.ndarray:
    """Signed hours from each time in `index` to the nearest high water in `highs` (+ = coming, - = past).
    NaN where none lies within MAX_HOURS_TO_HIGH. Ties go to the coming high."""
    highs = np.sort(np.asarray(highs, dtype="datetime64[ns]"))
    times = index.to_numpy()
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
    return nearest


def tide_at(hourly: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    """tide_height_m and hours_to_high_tide valid at each time in `index` (any sub-hourly grid), from the
    hourly table of `tide_features` (columns time_local, tide_height_m, hours_to_high_tide).

    Why evaluating between the hours is allowed: the table is a model product (Open-Meteo marine
    `sea_level_height_msl`: tides plus inverted-barometer and sea-surface-height effects, with harmonic gap fill),
    not a gauge observation. It is available as a forecast ahead of t (build_tide --refresh fetches up to today + 3 d),
    so the value at t, and the hour after it, is known at t: no look-ahead. Reading the 09:00 value at 09:45
    would be up to 45 min stale while the tide moves ~0.5 m/h. Archived past values differ slightly from what the
    forecast showed live (non-harmonic part: ~4.7 cm/h std, against ~0.5 m/h of tidal movement). If a column here
    ever becomes a real observation, do not interpolate it towards the next hour.

    Height: linear in time between the hourly values (error vs the true curve ~2 cm RMS for the 12.4 h tide). Times
    next to a NaN hour or a missing row (table rows more than 1 h apart) are NaN, never bridged.
    Hours to high: the high-water times are recovered from the hourly column (hour + hours_to_high_tide, which
    already come from the sub-hourly harmonic fit with the phase shift) and the nearest one is re-evaluated at
    each time. NaN outside the table's span or beyond MAX_HOURS_TO_HIGH.
    Timestamps are compared in nanoseconds, so table and grid may carry different datetime units."""
    h = hourly.drop_duplicates("time_local").set_index("time_local").sort_index()
    hours = pd.DatetimeIndex(h.index).as_unit("ns")
    index = pd.DatetimeIndex(index).as_unit("ns")
    height = h["tide_height_m"].to_numpy(float)
    ok = ~np.isnan(height)
    out_h = np.full(len(index), np.nan)
    if ok.sum() >= 2:
        out_h = np.interp(index.asi8.astype(float), hours.asi8[ok].astype(float), height[ok], left=np.nan, right=np.nan)
        # a gap must not be bridged by the line: both bracketing rows must be valid and at most one hour apart
        pos = np.clip(np.searchsorted(hours.asi8, index.asi8, side="right") - 1, 0, len(hours) - 1)
        nxt = np.minimum(pos + 1, len(hours) - 1)
        exact = hours.asi8[pos] == index.asi8
        adjacent = (ok[pos] & ok[nxt]) & (hours.asi8[nxt] - hours.asi8[pos] <= 3_600_000_000_000)
        out_h = np.where(exact | adjacent, out_h, np.nan)
    rel = h["hours_to_high_tide"].to_numpy(float)
    keep = ~np.isnan(rel)
    highs = np.unique((hours[keep] + pd.to_timedelta(np.round(rel[keep] * 3600), unit="s")).to_numpy())
    in_span = (index >= hours.min()) & (index <= hours.max())
    to_high = np.where(in_span, hours_to_nearest_high(index, highs), np.nan)
    return pd.DataFrame({"tide_height_m": out_h, "hours_to_high_tide": to_high}, index=index)

def tide_features(series: pd.Series, filled: pd.Series | None = None, fit: HarmonicFit | None = None,
                  phase_shift_min: float = TIDE_PHASE_SHIFT_MIN) -> pd.DataFrame:
    """tide_height_m, signed hours to the nearest high tide (+ = coming, - = past) and `tide_filled`
    (True where the hour came from the harmonic fit, `filled` aligned to `series`; all False if omitted).

    Without `fit`: high tides are the whole-hour local maxima of `series` (no shift).
    With `fit` (see `fit_harmonics`): high tides come from the fit at 5-minute resolution, shifted later by
    `phase_shift_min` (default TIDE_PHASE_SHIFT_MIN), so hours_to_high_tide is fractional.
    tide_height_m is always the series itself (not shifted, not rescaled).
    Where no high tide lies within MAX_HOURS_TO_HIGH, hours_to_high_tide is NaN."""
    if fit is not None:
        highs = high_water_times_subhourly(fit, series.index.min(), series.index.max(), phase_shift_min).to_numpy()
    else:
        highs = high_tide_times(series).to_numpy()
    nearest = hours_to_nearest_high(series.index, highs)
    return pd.DataFrame({"time_local": series.index, "tide_height_m": series.to_numpy(),
                         "hours_to_high_tide": nearest,
                         "tide_filled": (filled.reindex(series.index, fill_value=False).to_numpy(bool)
                                         if filled is not None else np.zeros(len(series), bool))})

def load_cached(raw_dir: Path) -> pd.Series:
    """All cached marine chunks in `raw_dir`; where chunks overlap (a later, longer download) the latest file wins."""
    from . import storage
    parts = [series_from_marine(json.loads(storage.read_raw(p))) for p in sorted(Path(raw_dir).glob("*.json.gz"))]
    series = pd.concat(parts[::-1])
    return series[~series.index.duplicated()].sort_index()


def build_hourly_table(raw_dir: Path, out_path: Path) -> pd.DataFrame:
    """Rebuild the hourly tide table (tide_features with the sub-hourly +shifted high waters) from the cached raw
    chunks and write it to `out_path` atomically (a reader never sees a half-written file)."""
    series = load_cached(raw_dir)
    filled, mask = fill_gaps(series)
    features = tide_features(filled, mask, fit=fit_harmonics(series))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_name(out_path.name + ".tmp")
    features.to_parquet(tmp, index=False)
    tmp.replace(out_path)
    return features


class TideTable:
    """The hourly tide parquet, re-read whenever its modification time changes (one stat per `get`).
    A missing file gives None; an unreadable new file keeps the previous table."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._mtime: int | None = None
        self._table: pd.DataFrame | None = None

    def get(self) -> pd.DataFrame | None:
        try:
            mtime = self.path.stat().st_mtime_ns
        except OSError:
            return self._table
        if mtime != self._mtime:
            self._mtime = mtime          # a bad file is logged once, not on every tick
            try:
                self._table = pd.read_parquet(self.path)
            except Exception:
                logging.getLogger(__name__).exception("tide table %s unreadable, keeping the previous one", self.path)
        return self._table
