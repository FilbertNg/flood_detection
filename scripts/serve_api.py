"""Run the Flood-Ready Township API locally (live mode + replay control).

Usage: python scripts/serve_api.py [--port 8000]
Then: http://localhost:8000/docs   (interactive API docs)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    uvicorn.run("floodready.api.app:app", host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
