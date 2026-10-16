"""G3: hourly tide for Port Klang → data/interim/tide_hourly.parquet.

Open-Meteo Marine has no data for some stretches (13-19 Jun 2024, 29 Jan-9 Feb 2025). Those hours
are filled with a harmonic fit to the rest of the series and marked `tide_filled`.

Usage: python scripts/build_tide.py            # re-parse the cached raw JSON in data/raw/tide
       python scripts/build_tide.py --refresh  # download 2024-01-01 → 3 days ahead first
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from floodready import storage, tide  # noqa: E402
from floodready.http import fetch_text, make_session  # noqa: E402

RAW = ROOT / "data" / "raw" / "tide"


def download() -> None:
    session = make_session()
    end = date.today() + timedelta(days=3)
    start = date(2024, 1, 1)
    while start <= end:
        chunk_end = min(date(start.year, 12, 31), end)
        text = fetch_text(session, tide.MARINE_URL, tide.marine_params(start.isoformat(), chunk_end.isoformat()))
        storage.save_raw(RAW / f"{start:%Y%m%d}_{chunk_end:%Y%m%d}.json.gz", text)
        start = chunk_end + timedelta(days=1)


def load_cached() -> pd.Series:
    """All cached chunks; where chunks overlap (a later, longer download) the latest file wins."""
    parts = [tide.series_from_marine(json.loads(storage.read_raw(p))) for p in sorted(RAW.glob("*.json.gz"))]
    series = pd.concat(parts[::-1])
    return series[~series.index.duplicated()].sort_index()


def main() -> None:
    if "--refresh" in sys.argv:
        download()
    series = load_cached()
    filled, mask = tide.fill_gaps(series)
    out = ROOT / "data" / "interim" / "tide_hourly.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    features = tide.tide_features(filled, mask, fit=tide.fit_harmonics(series))  # high waters: 5-min fit, +40 min (docs/tide-check.md)
    features.to_parquet(out, index=False)
    print(f"{len(features)} hours, {mask.sum()} filled ({mask.mean():.1%}), "
          f"{series.index.min()} → {series.index.max()} → {out.relative_to(ROOT)}")
    print(f"hours_to_high_tide: min {features.hours_to_high_tide.min():.2f}, max {features.hours_to_high_tide.max():.2f}, "
          f"NaN {features.hours_to_high_tide.isna().sum()}")
    for start in ("2024-11-05", "2025-08-10"):
        v = tide.holdout_validation(series, start, days=10)
        print(f"hold-out {start} +10 d: RMSE {v['rmse_m']:.3f} m (series std {v['series_std_m']:.3f}), bias {v['bias_m']:+.3f} m, "
              f"high-water timing mean |err| {v['timing_mean_abs_h']:.2f} h, max {v['timing_max_abs_h']:.2f} h "
              f"({v['n_highs_matched']}/{v['n_highs']} highs matched)")
    day = features.set_index("time_local").loc["2024-11-12 06:00":"2024-11-12 15:00"]
    print("12 Nov 2024:", [(t.strftime("%H"), round(h, 2), hh) for t, h, hh in zip(day.index, day.tide_height_m, day.hours_to_high_tide)])


if __name__ == "__main__":
    main()
