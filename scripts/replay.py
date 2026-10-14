"""E6 / milestone M1: replay a past event through the engine and print the timeline.

Usage:
  python scripts/replay.py --event 2024-11-12                     # BBR, 06:00-14:00
  python scripts/replay.py --event 2025-04-23 --township USJ --from 03:00 --to 09:00
Needs: data/raw/jps_hist (archive), data/interim/stations.parquet, assets/geo/<township>_streets.geojson.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import geopandas as gpd
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from floodready.engine import replay  # noqa: E402
from floodready.engine.types import Level  # noqa: E402


def load_yaml(name: str) -> dict:
    return yaml.safe_load((ROOT / "config" / name).read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True, help="date, e.g. 2024-11-12")
    parser.add_argument("--township", default="BBR")
    parser.add_argument("--from", dest="start", default="06:00")
    parser.add_argument("--to", dest="end", default="14:00")
    args = parser.parse_args()

    town = next(t for t in load_yaml("townships.yaml")["townships"] if t["id"] == args.township)
    station_ids = [s["graph_id"] for s in town["stations"]]
    start = datetime.fromisoformat(f"{args.event} {args.start}")
    end = datetime.fromisoformat(f"{args.event} {args.end}")
    readings = replay.load_archive_readings(ROOT / "data" / "raw" / "jps_hist", station_ids, start - timedelta(hours=26), end)
    stations = pd.read_parquet(ROOT / "data" / "interim" / "stations.parquet")
    streets = gpd.read_file(ROOT / "assets" / "geo" / f"{args.township.lower()}_streets.geojson")[["street_id", "name", "susceptibility"]]
    names = dict(zip(streets.street_id, streets.name))

    print(f"Replay {args.township} {args.event} {args.start}-{args.end}: {len(streets)} streets, "
          f"{readings.graph_id.nunique()} stations with data")
    last_line, total_alerts = None, Counter()
    for step in replay.run(start, end, timedelta(minutes=15), readings, stations, streets, station_ids,
                           load_yaml("rules.yaml"), load_yaml("risk_matrix.yaml")["matrix"]):
        counts = Counter(s.level for s in step.states)
        summary = " ".join(f"{lv.json}:{counts[lv]}" for lv in (Level.WATCH, Level.WARNING, Level.DANGER) if counts[lv])
        reason = step.trigger.reasons[0].text_en if step.trigger.reasons else ""
        line = (step.trigger.level, summary)
        for alert in step.alerts:
            total_alerts[(alert.kind, alert.level.json)] += 1
        if line != last_line:
            fired = ",".join(step.trigger.fired_by) or "-"
            print(f"{step.time:%H:%M}  {step.trigger.level.json.upper():8s} [{fired:20s}] streets {summary or 'all normal':40s} {reason}")
            last_line = line
        new_alerts = [a for a in step.alerts if a.kind == "alert"]
        if new_alerts:
            sample = ", ".join(names.get(a.street_id, a.street_id) for a in new_alerts[:3])
            print(f"         -> {len(new_alerts)} street alert(s) ({new_alerts[0].level.json}), e.g. {sample}")
    print("alerts issued:", dict(total_alerts))


if __name__ == "__main__":
    main()
