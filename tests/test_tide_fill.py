"""Harmonic gap fill for the tide series (improvement #7)."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from floodready import tide


def semidiurnal(hours=72):
    idx = pd.date_range("2024-11-12 00:00", periods=hours, freq="h")
    return pd.Series(2.0 * np.cos(2 * np.pi * (np.arange(hours) - 2) / 12), index=idx)


def synthetic_tide(days=120, start="2024-01-01"):
    """Known constituents: mean 0.3 + M2 1.2 + S2 0.5 + K1 0.4 + O1 0.3 + M4 0.05, arbitrary phases."""
    idx = pd.date_range(start, periods=days * 24, freq="h")
    hours = np.asarray((idx - tide._EPOCH) / pd.Timedelta(hours=1), dtype=float)
    parts = {"M2": (1.2, 40), "S2": (0.5, 200), "K1": (0.4, 75), "O1": (0.3, 310), "M4": (0.05, 10)}
    y = np.full(len(idx), 0.3)
    for name, (amp, phase) in parts.items():
        y += amp * np.cos(np.radians(tide.CONSTITUENTS_DEG_PER_H[name]) * hours - np.radians(phase))
    return pd.Series(y, index=idx, name="tide_height_m"), parts


def test_harmonic_fit_recovers_known_constituents():
    series, parts = synthetic_tide()
    fit = tide.fit_harmonics(series)
    amps = fit.amplitudes()
    for name, (amp, _) in parts.items():
        assert abs(amps[name] - amp) < 1e-6
    assert abs(fit.coefficients[0] - 0.3) < 1e-6
    for name in ("N2", "K2", "P1", "Q1", "MS4"):
        assert amps[name] < 1e-6
    assert set(amps) >= {"M2", "S2", "N2", "K2", "K1", "O1", "P1", "Q1", "M4", "MS4"}
    assert np.allclose(fit.predict(series.index), series, atol=1e-6)


def test_fit_ignores_nan_and_needs_enough_data():
    series, _ = synthetic_tide()
    series.iloc[500:900] = np.nan
    assert abs(tide.fit_harmonics(series).amplitudes()["M2"] - 1.2) < 1e-6
    with pytest.raises(ValueError):
        tide.fit_harmonics(series.iloc[:10])


def test_fill_gaps_fills_only_missing_hours_and_marks_them():
    series, _ = synthetic_tide()
    truth = series.copy()
    series.iloc[1000:1144] = np.nan                      # a 6-day gap
    series = series.drop(series.index[2000:2010])        # hours absent from the index entirely
    filled, mask = tide.fill_gaps(series)
    assert not filled.isna().any() and len(filled) == len(truth)
    assert mask.sum() == 144 + 10
    assert mask.iloc[1000:1144].all() and mask.iloc[2000:2010].all()
    assert np.allclose(filled[mask], truth[mask], atol=1e-6)          # exact for an exact-harmonic series
    observed = series.dropna()
    assert (filled[observed.index] == observed).all()                 # observed hours untouched


def test_holdout_validation_on_exact_harmonics_has_no_error():
    series, _ = synthetic_tide()
    v = tide.holdout_validation(series, "2024-03-01", days=10)
    assert v["rmse_m"] < 1e-6 and v["n_highs_matched"] == v["n_highs"] > 15
    assert v["timing_max_abs_h"] == 0


def test_hours_to_high_tide_stays_within_7h_across_a_gap():
    series, _ = synthetic_tide()
    series.iloc[1000:1432] = np.nan                      # 18 days, like the real 432 h gap
    assert tide.tide_features(series).hours_to_high_tide.abs().max() <= 7   # NaN rather than extrapolated
    filled, mask = tide.fill_gaps(series)
    after = tide.tide_features(filled, mask)
    assert after.hours_to_high_tide.abs().max() <= 7
    gap = after.iloc[1000:1432]
    assert gap.hours_to_high_tide.notna().all() and gap.tide_filled.all() and gap.tide_height_m.notna().all()
    assert after.tide_filled.sum() == 432


def test_tide_filled_column_defaults_to_false():
    assert not tide.tide_features(semidiurnal()).tide_filled.any()


def test_unfilled_gap_gives_nan_not_extrapolated_hours():
    series = semidiurnal(hours=24 * 20)
    series.iloc[100:400] = np.nan
    f = tide.tide_features(series)
    assert f.hours_to_high_tide.abs().max() <= tide.MAX_HOURS_TO_HIGH
    assert f.hours_to_high_tide.iloc[200:300].isna().any()


def test_rebuilt_tide_file_has_no_gap_nonsense():
    path = Path(__file__).resolve().parents[1] / "data" / "interim" / "tide_hourly.parquet"
    if not path.exists():
        pytest.skip("data/interim/tide_hourly.parquet not built")
    df = pd.read_parquet(path)
    if "tide_filled" not in df.columns:
        pytest.skip("tide file predates the gap fill; run scripts/build_tide.py")
    assert df.tide_filled.dtype == bool and df.tide_filled.sum() > 0
    assert df.hours_to_high_tide.abs().max() <= 7 and df.tide_height_m.notna().all()
