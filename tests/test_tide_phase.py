"""Sub-hourly high-water timing and the +40 min phase correction (WP7 tide check)."""
import numpy as np
import pandas as pd

from floodready import tide
from tests.test_tide_fill import synthetic_tide


def test_default_phase_shift_is_40_minutes_later():
    assert tide.TIDE_PHASE_SHIFT_MIN == 40.0


def test_subhourly_highs_match_the_known_constituent_peak_without_hour_rounding():
    series, _ = synthetic_tide(days=60)
    fit = tide.fit_harmonics(series)
    unshifted = tide.high_water_times_subhourly(fit, series.index[0], series.index[-1], phase_shift_min=0)
    truth_grid = pd.date_range("2024-02-01", "2024-02-03", freq="1min")
    truth = pd.Series(fit.predict(truth_grid).to_numpy(), index=truth_grid)
    true_highs = truth.index[(truth > truth.shift(1)) & (truth >= truth.shift(-1))]
    for t in true_highs:
        nearest = unshifted[np.argmin(np.abs((unshifted - t) / pd.Timedelta(minutes=1)))]
        assert abs((nearest - t) / pd.Timedelta(minutes=1)) <= 2.5          # 5-min grid
    assert any(t.minute % 60 not in (0,) for t in unshifted)                 # not whole hours


def test_phase_shift_moves_every_high_water_later_by_that_amount():
    series, _ = synthetic_tide(days=30)
    fit = tide.fit_harmonics(series)
    a = tide.high_water_times_subhourly(fit, series.index[0], series.index[-1], phase_shift_min=0)
    b = tide.high_water_times_subhourly(fit, series.index[0], series.index[-1], phase_shift_min=40)
    d = [(b[np.argmin(np.abs((b - t) / pd.Timedelta(minutes=1) - 40))] - t) / pd.Timedelta(minutes=1) for t in a[5:-5]]
    assert all(abs(x - 40) <= 5 for x in d)


def test_hours_to_high_tide_uses_the_shifted_subhourly_highs():
    series, _ = synthetic_tide(days=30)
    fit = tide.fit_harmonics(series)
    plain = tide.tide_features(series, fit=fit, phase_shift_min=0).set_index("time_local").hours_to_high_tide
    shifted = tide.tide_features(series, fit=fit).set_index("time_local").hours_to_high_tide
    mid = series.index[200:500]
    # highs later by 40 min: while a high is still ahead, time to it grows by 40 min; fractional values appear
    ahead = (plain.loc[mid] > 0) & (plain.loc[mid] < 5)
    assert np.allclose((shifted.loc[mid] - plain.loc[mid])[ahead], 40 / 60, atol=0.1)
    assert (shifted.abs() <= 7).all() and shifted.notna().all()
    assert (shifted.dropna() % 1 != 0).any()


def test_height_column_is_not_shifted_or_rescaled():
    series, _ = synthetic_tide(days=30)
    f = tide.tide_features(series, fit=tide.fit_harmonics(series))
    assert np.array_equal(f.tide_height_m.to_numpy(), series.to_numpy())
