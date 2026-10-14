import numpy as np
import pandas as pd

from floodready import tide


def semidiurnal(hours=72):
    """Synthetic tide: highs every 12 h at 02:00 and 14:00."""
    idx = pd.date_range("2024-11-12 00:00", periods=hours, freq="h")
    t = np.arange(hours)
    return pd.Series(2.0 * np.cos(2 * np.pi * (t - 2) / 12), index=idx)


def test_high_tides_are_the_local_maxima():
    highs = tide.high_tide_times(semidiurnal())
    assert pd.Timestamp("2024-11-12 02:00") in highs and pd.Timestamp("2024-11-12 14:00") in highs
    assert all(h.hour in (2, 14) for h in highs)


def test_hours_to_high_tide_is_signed_distance_to_nearest_high():
    features = tide.tide_features(semidiurnal())
    at = features.set_index("time_local")
    assert at.loc["2024-11-12 02:00", "hours_to_high_tide"] == 0
    assert at.loc["2024-11-12 11:00", "hours_to_high_tide"] == 3      # next high at 14:00
    assert at.loc["2024-11-12 04:00", "hours_to_high_tide"] == -2     # last high was 02:00
    assert at.loc["2024-11-12 02:00", "tide_height_m"] == 2.0


def test_flatten_marine_response():
    payload = {"hourly": {"time": ["2024-11-12T00:00", "2024-11-12T01:00"], "sea_level_height_msl": [1.5, None]}}
    series = tide.series_from_marine(payload)
    assert series.index[0] == pd.Timestamp("2024-11-12 00:00")
    assert series.iloc[0] == 1.5 and np.isnan(series.iloc[1])
