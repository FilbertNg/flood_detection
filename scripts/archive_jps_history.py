"""T4: archive JPS Infobanjir station history (rain from Jan 2024, water level from Apr 2024).

Township stations first, then stations by district (config/sources.yaml).
Resumable: every monthly chunk is cached, so just run it again after a stop.

Usage:
  python scripts/archive_jps_history.py              # all selected stations
  python scripts/archive_jps_history.py --limit 10   # first 10 station/kind pairs only
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from floodready import infobanjir as ib  # noqa: E402
from floodready import jobs  # noqa: E402
from floodready.http import fetch_text, make_session  # noqa: E402

DATA = ROOT / "data" / "raw"
log = logging.getLogger("archive")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    (ROOT / "logs").mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(ROOT / "logs" / "archive.log", encoding="utf-8"),
                  logging.StreamHandler()],
    )
    sources = yaml.safe_load((ROOT / "config" / "sources.yaml").read_text(encoding="utf-8"))
    townships = yaml.safe_load((ROOT / "config" / "townships.yaml").read_text(encoding="utf-8"))["townships"]
    hist = sources["jps_history"]
    session = make_session()

    wl_rows, rf_rows = [], []
    for state in sources["jps_live"]["states"]:
        wl_rows += ib.parse_wl_live(fetch_text(session, ib.WL_LIVE_URL, ib.wl_live_params(state)), state)
        rf_rows += ib.parse_rf_live(fetch_text(session, ib.RF_LIVE_URL, ib.rf_live_params(state)), state)
    order = jobs.select_archive_stations(wl_rows, rf_rows, townships, hist["districts"])
    if args.limit:
        order = order[: args.limit]
    log.info("archiving %d station/kind pairs", len(order))

    starts = {"rf": date.fromisoformat(str(hist["rain_from"])), "wl": date.fromisoformat(str(hist["wl_from"]))}
    today = jobs.now_myt().date()
    results = []
    for i, (graph_id, kind) in enumerate(order, 1):
        summary = jobs.archive_station_history(session, DATA, graph_id, kind, starts[kind], today,
                                               pause_s=hist["pause_s"])
        log.info("[%d/%d] %s", i, len(order), summary)
        results.append(summary)
        (DATA / "jps_hist").mkdir(parents=True, exist_ok=True)
        (DATA / "jps_hist" / "_progress.json").write_text(json.dumps(
            {"done": i, "total": len(order), "last": summary}, indent=2))
    failed = [r for r in results if r["failed"]]
    log.info("finished: %d pairs, %d with failed chunks (re-run to retry)", len(results), len(failed))


if __name__ == "__main__":
    main()
