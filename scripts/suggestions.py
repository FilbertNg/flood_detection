"""Compute improvement suggestions SUG-1..7 for a period and upsert them into the suggestions table (WP7).

Usage:
  python scripts/suggestions.py --from 2024-11-01 --to 2024-11-30 --township BBR \
      --db sqlite:///suggestions_test.db --data-dir "<repo>/data"

Reads alerts, answers and sensor readings from the database, and the JPS history archive under --data-dir (READ ONLY)
for rain at flood onset and station health. Replay alerts, demo answers and simulated sensor readings are ignored.
Ids are deterministic (`s_<rule>_<street or station>_<period>`), so a re-run updates rows and keeps their admin
status and notes. News events are used only when --events is given (the labels are drafts until a human checks them).
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from floodready.db import repo  # noqa: E402
from floodready.engine import replay, street_stations  # noqa: E402
from floodready.ml import dataset  # noqa: E402
from floodready.stats import suggestions as sug  # noqa: E402

RAIN_WINDOW = timedelta(hours=3)


def make_onset_rain(readings: pd.DataFrame, mapping: dict | None):
    """onset_rain(street, t): the highest 3 h rain total (ending at t) among the street's rain gauges, from QC-cleaned
    archive readings; None when the street has no gauge mapping or no valid reading in that window."""
    rf = readings[readings["kind"] == "rf"]
    series = {g: s.set_index("time_local")["rain_15min_mm"].sort_index() for g, s in rf.groupby("graph_id")}

    def onset_rain(street_id: str, t: datetime) -> float | None:
        entry = (mapping or {}).get(street_id)
        totals = []
        for g in (entry or {}).get("rf", []):
            s = series.get(g)
            if s is None:
                continue
            w = s.loc[pd.Timestamp(t) - RAIN_WINDOW + pd.Timedelta(seconds=1):pd.Timestamp(t)].dropna()
            if len(w):
                totals.append(float(w.sum()))
        return max(totals) if totals else None

    return onset_rain


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--from", dest="start", required=True, type=date.fromisoformat)
    p.add_argument("--to", dest="end", required=True, type=date.fromisoformat)
    p.add_argument("--township", default="BBR")
    p.add_argument("--db", default=os.environ.get("DATABASE_URL", "sqlite:///data/floodready.db"))
    p.add_argument("--data-dir", type=Path, default=ROOT / "data", help="folder with raw/jps_hist and interim/ (read only)")
    p.add_argument("--events", type=Path, default=None, help="labelled news events CSV (draft labels: only if you checked them)")
    p.add_argument("--dry-run", action="store_true", help="print the suggestions, write nothing")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    town = next(t for t in yaml.safe_load((ROOT / "config" / "townships.yaml").read_text(encoding="utf-8"))["townships"]
                if t["id"] == args.township)
    data = Path(args.data_dir)
    stations = pd.read_parquet(data / "interim" / "stations.parquet")
    tide_path = data / "interim" / "tide_hourly.parquet"
    tide = pd.read_parquet(tide_path) if tide_path.exists() else None
    hist = data / "raw" / "jps_hist"
    archived = {q.stem for q in (hist / "rf").glob("*.parquet")} | {q.stem for q in (hist / "wl").glob("*.parquet")}
    ids = dataset.township_station_ids(town, stations, archived)
    start_dt = datetime.combine(args.start, datetime.min.time())
    end_dt = datetime.combine(args.end + timedelta(days=1), datetime.min.time()) - timedelta(minutes=15)
    readings = replay.load_archive_readings(hist, ids, start_dt - timedelta(days=1), end_dt, stations=stations)

    own = [s["graph_id"] for s in town["stations"]]
    names = {s["graph_id"]: s["name"] for s in town["stations"]}
    health = sug.station_health(readings[readings["graph_id"].isin(own)], args.start, args.end, names=names)
    stat_names = dict(zip(stations['graph_id'], stations['name'])) | names
    mapping = street_stations.load(ROOT / "assets" / "geo" / f"{args.township.lower()}_street_stations.json")
    events = pd.read_csv(args.events) if args.events else None

    engine = repo.connect(args.db)
    with engine.begin() as conn:
        out = sug.suggestions(conn, args.start, args.end, tide, health, onset_rain=make_onset_rain(readings, mapping),
                              events=events, street_stations=mapping, station_names=stat_names)
        if not args.dry_run:
            sug.save(conn, out, args.start, args.end)

    print(f"{args.township} {args.start}..{args.end}: {len(out)} suggestions"
          f"{' (dry run, nothing written)' if args.dry_run else ' upserted'}")
    by_rule: dict[str, int] = {}
    for s in out:
        by_rule[s["rule"]] = by_rule.get(s["rule"], 0) + 1
    print("by rule: " + (", ".join(f"{r}={n}" for r, n in sorted(by_rule.items())) or "none"))
    print("station health (stale %): " + ", ".join(f"{h['graph_id']}={h['stale_pct']}" for h in health))
    for s in out[:12]:
        print(f"  [{s['priority']:6s}] {s['rule']} {s['id']}: {s['text']}")


if __name__ == "__main__":
    main()
