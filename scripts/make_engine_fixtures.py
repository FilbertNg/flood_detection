"""E1: real-data fixtures for the engine tests (12 Nov 2024, Bandar Bukit Raja).

Writes tests/fixtures/engine/bbr_20241112_readings.csv (all BBR named stations,
rain + water level, 2024-11-11 00:00 → 2024-11-12 23:45) and stations.csv.
Run after the JPS history archive and scripts/build_station_lookup.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
HIST = ROOT / "data" / "raw" / "jps_hist"
OUT = ROOT / "tests" / "fixtures" / "engine"


def main() -> None:
    town = next(t for t in yaml.safe_load((ROOT / "config" / "townships.yaml").read_text(encoding="utf-8"))["townships"]
                if t["id"] == "BBR")
    ids = [s["graph_id"] for s in town["stations"]]
    frames = []
    for kind, value in (("rf", "rain_15min_mm"), ("wl", "wl_m")):
        for graph_id in ids:
            path = HIST / kind / f"{graph_id}.parquet"
            if not path.exists():
                continue
            df = pd.read_parquet(path)
            df = df[(df.time_local >= "2024-11-11 00:00") & (df.time_local <= "2024-11-12 23:45")]
            frames.append(pd.DataFrame({"graph_id": graph_id, "kind": kind, "time_local": df.time_local, value: df[value]}))
    readings = pd.concat(frames, ignore_index=True)[["graph_id", "kind", "time_local", "rain_15min_mm", "wl_m"]]
    lookup = pd.read_parquet(ROOT / "data" / "interim" / "stations.parquet")
    present = readings[["graph_id", "kind"]].drop_duplicates()
    station_rows = lookup.merge(present, on=["graph_id", "kind"])
    OUT.mkdir(parents=True, exist_ok=True)
    readings.sort_values(["graph_id", "kind", "time_local"]).to_csv(OUT / "bbr_20241112_readings.csv", index=False)
    station_rows.to_csv(OUT / "stations.csv", index=False)
    print(f"{len(readings)} readings for {len(present)} station/kind pairs → {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
