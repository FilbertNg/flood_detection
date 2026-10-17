"""Create every Flood-Ready table in a database (idempotent).

Usage: python scripts/db_init.py --url sqlite:///data/floodready.db
       python scripts/db_init.py --url "$DATABASE_URL"        # Postgres needs: pip install -e ".[postgres]"
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import inspect  # noqa: E402

from floodready.db import repo  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=os.environ.get("DATABASE_URL", "sqlite:///data/floodready.db"))
    args = parser.parse_args()
    if args.url.startswith("sqlite:///") and not args.url.startswith("sqlite:///:"):
        Path(args.url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    engine = repo.connect(args.url)
    print(f"{engine.url.render_as_string(hide_password=True)}: {len(inspect(engine).get_table_names())} tables")


if __name__ == "__main__":
    main()
