"""Create (or update) an Admin app account. Nothing is stored in the repo: the hash goes into the database only.

Usage:
  python scripts/seed_admin.py --email you@example.org --role admin           # password from $ADMIN_PASSWORD or a prompt
  ADMIN_EMAIL=you@example.org ADMIN_PASSWORD=... python scripts/seed_admin.py
  python scripts/seed_admin.py --email viewer@example.org --role viewer --url sqlite:///data/floodready.db

Roles: admin (can write: suggestions, review, notes, replay) or viewer (read only). Re-running with the same email
replaces the password and role. Passwords: 1 to 72 bytes (bcrypt limit). Relative sqlite paths are relative to the
repo, like the API's DATABASE_URL.
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from floodready.api import auth  # noqa: E402
from floodready.db import repo  # noqa: E402


def database_url(url: str) -> str:
    if url.startswith("sqlite:///") and not url.startswith("sqlite:////") and ":memory:" not in url:
        path = ROOT / url.removeprefix("sqlite:///")
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path.as_posix()}"
    return url


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email", default=os.environ.get("ADMIN_EMAIL"))
    parser.add_argument("--role", choices=auth.ROLES, default="admin")
    parser.add_argument("--password", help="avoid: it lands in your shell history; use $ADMIN_PASSWORD or the prompt")
    parser.add_argument("--url", default=os.environ.get("DATABASE_URL", "sqlite:///data/floodready.db"))
    args = parser.parse_args(argv)
    if not args.email:
        parser.error("--email (or $ADMIN_EMAIL) is required")
    password = args.password or os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Password: ")
    try:
        engine = repo.connect(database_url(args.url))
        with engine.begin() as conn:
            auth.create_user(conn, args.email, password, args.role)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"{args.role} {args.email.strip().lower()} saved in {engine.url.render_as_string(hide_password=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
