"""Rebuild the logged live tables from the saved raw pages (latest copy of each reading wins).

Usage: python scripts/rebuild_live_tables.py              # every logged day
       python scripts/rebuild_live_tables.py 2026-10-15   # one day
Stop scripts/run_loggers.py first so it doesn't write while the files are rebuilt.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from floodready import jobs  # noqa: E402

DATA = ROOT / "data" / "raw"

if __name__ == "__main__":
    days = sys.argv[1:] or sorted(p.name for p in (DATA / "jps_live" / "html").iterdir() if p.is_dir())
    for day in days:
        print(day, jobs.rebuild_live_day(DATA, day))
