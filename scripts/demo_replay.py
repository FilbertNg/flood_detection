"""Start (or stop) a replay of a past flood on a running API, for demos.

Usage:
  python scripts/demo_replay.py --event 2024-11-12 --speed 120           # 15-min steps every 7.5 s
  python scripts/demo_replay.py --event 2024-11-12 --speed 0 --stop-at 09:00   # jump straight to 09:00
  python scripts/demo_replay.py --stop                                     # back to live
Login comes from ADMIN_EMAIL / ADMIN_PASSWORD (dev defaults when unset, matching the API).
"""
from __future__ import annotations

import argparse
import os

import requests


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default=os.environ.get("API_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--event", default="2024-11-12")
    parser.add_argument("--speed", type=float, default=120)
    parser.add_argument("--start", default="06:00")
    parser.add_argument("--end", default="14:00")
    parser.add_argument("--stop-at", default=None)
    parser.add_argument("--stop", action="store_true")
    args = parser.parse_args()

    email = os.environ.get("ADMIN_EMAIL", "admin@floodready.local")
    password = os.environ.get("ADMIN_PASSWORD", "floodready-demo")
    token = requests.post(f"{args.api}/api/v1/admin/login", json={"email": email, "password": password}, timeout=30).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    if args.stop:
        response = requests.delete(f"{args.api}/api/v1/admin/replay", headers=headers, timeout=60)
    else:
        body = {"event": args.event, "speed": args.speed, "start": args.start, "end": args.end, "stop_at": args.stop_at}
        response = requests.post(f"{args.api}/api/v1/admin/replay", json=body, headers=headers, timeout=300)
    response.raise_for_status()
    print(response.json())


if __name__ == "__main__":
    main()
