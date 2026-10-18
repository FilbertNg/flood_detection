"""Simulated water-level sensor: posts readings to POST /sensor/readings, always with simulated=true.

Usage: python scripts/sim_sensor.py --curve rise --steps 10 --interval 5 --token $SENSOR_TOKEN
Curves: flat (dry drain), rise (dry to well above the 15 cm threshold in config/rules.yaml), spike (short peak).
Simulated readings are labelled in the apps and excluded from statistics.
"""
from __future__ import annotations

import argparse
import os
import time

import requests

DEFAULT_URL = "http://localhost:8000/api/v1"
DRY_CM = 2.0
PEAK_CM = 45.0


def curve(name: str, steps: int) -> list[float]:
    """Water level in cm for `steps` readings."""
    if steps < 1:
        raise ValueError("steps must be >= 1")
    if name == "flat":
        return [DRY_CM] * steps
    frac = [i / max(steps - 1, 1) for i in range(steps)]
    if name == "rise":
        return [round(DRY_CM + (PEAK_CM - DRY_CM) * f, 1) for f in frac]
    if name == "spike":
        return [round(DRY_CM + (PEAK_CM - DRY_CM) * (1 - abs(2 * f - 1)), 1) for f in frac]
    raise ValueError(f"unknown curve {name}")


def run(argv: list[str] | None = None, post=requests.post, sleep=time.sleep) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--curve", choices=["flat", "rise", "spike"], default="rise")
    p.add_argument("--steps", type=int, default=10)
    p.add_argument("--interval", type=float, default=5.0, help="seconds between readings")
    p.add_argument("--url", default=os.environ.get("API_URL", DEFAULT_URL))
    p.add_argument("--token", default=os.environ.get("SENSOR_TOKEN", ""))
    p.add_argument("--device", default="sim-1")
    args = p.parse_args(argv)
    if not args.device.startswith("sim-"):
        p.error("--device must start with 'sim-' so simulated rows are recognisable")
    sent = 0
    for i, level in enumerate(curve(args.curve, args.steps)):
        r = post(f"{args.url}/sensor/readings", json={"device_id": args.device, "level_cm": level, "simulated": True},
                 headers={"Authorization": f"Bearer {args.token}"}, timeout=10)
        r.raise_for_status()
        sent += 1
        print(f"{i + 1}/{args.steps}: {level} cm (simulated)")
        if i < args.steps - 1:
            sleep(args.interval)
    return sent


if __name__ == "__main__":
    run()
