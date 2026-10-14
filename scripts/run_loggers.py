"""T2 + T3: live loggers for JPS Infobanjir, MET warnings and Open-Meteo forecasts.

Usage:
  python scripts/run_loggers.py          # run forever: JPS + MET every 15 min, forecast every hour
  python scripts/run_loggers.py --once   # one pass of everything (Task Scheduler / cron / CI)

Run it on an always-on machine; a sleeping laptop loses data that can't be recovered.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from floodready import jobs  # noqa: E402
from floodready.http import make_session  # noqa: E402

DATA = ROOT / "data" / "raw"
log = logging.getLogger("loggers")


def run_pass(session, cfg: dict, with_forecast: bool) -> None:
    now = jobs.now_myt()
    tasks = [
        ("jps_live", lambda: jobs.run_jps_live(session, DATA, cfg["jps_live"]["states"], now)),
        ("met_warnings", lambda: jobs.run_met_warnings(session, DATA, now)),
    ]
    if with_forecast:
        fc = cfg["openmeteo_forecast"]
        tasks.append(("forecast", lambda: jobs.run_forecast(session, DATA, fc["points"], fc["models"], now)))
    for name, task in tasks:
        try:
            log.info("%s %s", name, task())
        except Exception:
            log.exception("%s failed", name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    (ROOT / "logs").mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(ROOT / "logs" / "loggers.log", encoding="utf-8"),
                  logging.StreamHandler()],
    )
    cfg = yaml.safe_load((ROOT / "config" / "sources.yaml").read_text(encoding="utf-8"))
    session = make_session()

    if args.once:
        run_pass(session, cfg, with_forecast=True)
        return

    interval = cfg["jps_live"]["interval_min"] * 60
    last_forecast_hour = None
    while True:
        now = jobs.now_myt()
        hour = now.strftime("%Y-%m-%d %H")
        run_pass(session, cfg, with_forecast=hour != last_forecast_hour)
        last_forecast_hour = hour
        # Wake 2 min after each quarter hour, once JPS has published.
        wait = interval - (time.time() - 120) % interval
        time.sleep(wait)


if __name__ == "__main__":
    main()
