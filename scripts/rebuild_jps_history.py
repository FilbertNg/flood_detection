"""Rebuild the parsed JPS history parquet files from the cached raw chunks.

Run after a parser fix; nothing is downloaded. Don't run while
archive_jps_history.py is still writing.

Usage:
  python scripts/rebuild_jps_history.py            # every archived station
  python scripts/rebuild_jps_history.py --kind rf  # rainfall only
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from floodready import jobs  # noqa: E402

DATA = ROOT / "data" / "raw"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=["rf", "wl"], default=None)
    args = parser.parse_args()
    kinds = [args.kind] if args.kind else ["rf", "wl"]
    for kind in kinds:
        stations = sorted(p.name for p in (DATA / "jps_hist" / "raw" / kind).glob("*") if p.is_dir())
        for graph_id in stations:
            print(kind, graph_id, jobs.rebuild_history_parquet(DATA, kind, graph_id), "rows")


if __name__ == "__main__":
    main()
