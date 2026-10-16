"""T2 + T3: live loggers for JPS Infobanjir, MET warnings and Open-Meteo forecasts.

Usage:
  python scripts/run_loggers.py          # run forever: JPS + MET every 15 min, forecast every hour
  python scripts/run_loggers.py --once   # one pass of everything (Task Scheduler / cron / CI)
  python scripts/run_loggers.py --radar  # radar archive only, every radar.interval_min (needs radar.enabled)

The radar logger (WP8) is off unless config/sources.yaml has radar.enabled: true; see docs/radar-nowcast.md.

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
    if cfg.get("radar", {}).get("enabled"):
        tasks.append(("radar", lambda: jobs.run_radar(session, DATA, now)))
    for name, task in tasks:
        try:
            log.info("%s %s", name, task())
        except Exception:
            log.exception("%s failed", name)


TIDE_OUT = ROOT / "data" / "interim" / "tide_hourly.parquet"
TIDE_RAW = DATA / "tide"


def maybe_refresh_tide(session):
    """Once per day (and after a failure no sooner than 6 h later) re-download the marine tide up to today + 3 d and
    rebuild the hourly table the API and ML read. Failures are logged, never fatal."""
    now = jobs.now_myt()
    if not jobs.tide_refresh_due(TIDE_OUT, now, jobs.read_tide_attempt(TIDE_OUT)):
        return
    jobs.write_tide_attempt(TIDE_OUT, now)               # shared by loop and --once runs: no hammering after a failure
    try:
        log.info("tide_refresh %s", jobs.run_tide_refresh(session, TIDE_RAW, TIDE_OUT, now.date()))
    except Exception:
        log.exception("tide_refresh failed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--radar", action="store_true", help="only the radar archive, polled every radar.interval_min")
    args = parser.parse_args()

    (ROOT / "logs").mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(ROOT / "logs" / "loggers.log", encoding="utf-8"),
                  logging.StreamHandler()],
    )
    cfg = yaml.safe_load((ROOT / "config" / "sources.yaml").read_text(encoding="utf-8"))
    session = make_session()

    radar_cfg = cfg.get("radar", {})
    if args.radar:
        if not radar_cfg.get("enabled"):
            sys.exit("radar.enabled is false in config/sources.yaml (MET Malaysia consent needed, see docs/radar-nowcast.md)")
        while True:
            try:
                log.info("radar %s", jobs.run_radar(session, DATA, jobs.now_myt()))
            except Exception:
                log.exception("radar failed")
            time.sleep(radar_cfg.get("interval_min", 5) * 60)

    if args.once:
        run_pass(session, cfg, with_forecast=True)
        maybe_refresh_tide(session)
        return

    interval = cfg["jps_live"]["interval_min"] * 60
    last_forecast_hour = None
    while True:
        maybe_refresh_tide(session)
        now = jobs.now_myt()
        hour = now.strftime("%Y-%m-%d %H")
        run_pass(session, cfg, with_forecast=hour != last_forecast_hour)
        last_forecast_hour = hour
        # Wake 2 min after each quarter hour, once JPS has published.
        wait = interval - (time.time() - 120) % interval
        time.sleep(wait)


if __name__ == "__main__":
    main()
