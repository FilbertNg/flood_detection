"""E7: backfill past alerts (out-of-fold ML, rules decide levels) into the database, month by month.

Usage:
  python scripts/backfill.py --from 2024-11-01 --to 2024-11-30 --township BBR \
      --db sqlite:///backfill_test.db --data-dir "<repo>/data"
Idempotent: a re-run replaces the months it covers. Writes alerts only (is_backfill=1), never street states.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from floodready.db import repo  # noqa: E402
from floodready.engine import backfill  # noqa: E402


def _day(text: str, end: bool) -> datetime:
    d = datetime.fromisoformat(text)
    return d + timedelta(hours=23, minutes=45) if end and len(text) <= 10 else d


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--from", dest="start", required=True, help="date or datetime, e.g. 2024-01-01")
    p.add_argument("--to", dest="end", required=True, help="date (through 23:45) or datetime, e.g. 2026-10-17")
    p.add_argument("--township", default="BBR")
    p.add_argument("--db", default=os.environ.get("DATABASE_URL", "sqlite:///data/floodready.db"))
    p.add_argument("--data-dir", type=Path, default=ROOT / "data", help="folder with raw/jps_hist and interim/ (read only)")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    start, end = _day(args.start, False), _day(args.end, True)

    t0 = time.perf_counter()
    engine = repo.connect(args.db)
    backfill.run_backfill(start, end, args.township, engine, data_dir=args.data_dir)   # commits each month
    with engine.connect() as conn:
        counts = backfill.monthly_counts(conn, args.township)
    print(f"{'month':8s} {'watch':>7s} {'warning':>8s} {'danger':>7s}   (alert rows by level; all-clears not counted)")
    for month, by_level in counts.items():
        if args.start[:7] <= month <= args.end[:7]:
            print(f"{month:8s} {by_level.get('watch', 0):7d} {by_level.get('warning', 0):8d} {by_level.get('danger', 0):7d}")
    print(f"runtime {time.perf_counter() - t0:.0f} s")


if __name__ == "__main__":
    main()
