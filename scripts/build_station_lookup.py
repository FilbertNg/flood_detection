"""Station lookup (names, districts, thresholds, coordinates) → data/interim/stations.parquet.

Uses the newest Infobanjir live tables we logged plus the frozen data.gov.my
station list (data/raw/datagovmy/) for coordinates.

Usage: python scripts/build_station_lookup.py
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from floodready import stations  # noqa: E402


def latest_live(kind: str) -> pd.DataFrame:
    files = sorted(glob.glob(str(ROOT / "data" / "raw" / "jps_live" / kind / "*.parquet")))
    live = pd.concat(pd.read_parquet(f) for f in files[-3:])
    return live.sort_values("fetched_at_local").drop_duplicates("graph_id", keep="last")


def main() -> None:
    old_file = sorted(glob.glob(str(ROOT / "data" / "reference" / "datagovmy_flood_warning_stations_*.json")))[-1]
    old = pd.DataFrame(json.load(open(old_file, encoding="utf-8")))
    lookup = stations.build_lookup(latest_live("wl"), latest_live("rf"), old)
    out = ROOT / "data" / "interim" / "stations.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    lookup.to_parquet(out, index=False)
    for kind in ("wl", "rf"):
        part = lookup[lookup.kind == kind]
        print(f"{kind}: {len(part)} stations, {part.lat.notna().sum()} with coordinates"
              + (f", {(~part.thresholds_ok).sum()} with thresholds out of order" if kind == "wl" else ""))
    print(f"→ {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
