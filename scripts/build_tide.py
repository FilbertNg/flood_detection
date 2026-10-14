"""G3: hourly tide for Port Klang, 2024-01-01 → 3 days ahead → data/interim/tide_hourly.parquet.

Usage: python scripts/build_tide.py
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


def main() -> None:
    session = make_session()
    end = date.today() + timedelta(days=3)
    parts, start = [], date(2024, 1, 1)
    while start <= end:
        chunk_end = min(date(start.year, 12, 31), end)
        text = fetch_text(session, tide.MARINE_URL, tide.marine_params(start.isoformat(), chunk_end.isoformat()))
        storage.save_raw(ROOT / "data" / "raw" / "tide" / f"{start:%Y%m%d}_{chunk_end:%Y%m%d}.json.gz", text)
        parts.append(tide.series_from_marine(json.loads(text)))
        start = chunk_end + timedelta(days=1)
    series = pd.concat(parts)
    series = series[~series.index.duplicated()].sort_index()
    out = ROOT / "data" / "interim" / "tide_hourly.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    features = tide.tide_features(series)
    features.to_parquet(out, index=False)
    print(f"{len(features)} hours, {series.isna().mean():.1%} missing, {series.index.min()} → {series.index.max()} → {out.relative_to(ROOT)}")
    day = features.set_index("time_local").loc["2024-11-12 06:00":"2024-11-12 15:00"]
    print("12 Nov 2024:", [(t.strftime("%H"), round(h, 2), hh) for t, h, hh in zip(day.index, day.tide_height_m, day.hours_to_high_tide)])


if __name__ == "__main__":
    main()
