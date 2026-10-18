"""Generate a VAPID key pair for Web Push and write it to .env (gitignored). Never commit the keys.

python scripts/gen_vapid.py [--subject mailto:you@example.com] [--env .env] [--force]

An existing, complete key pair is kept unless --force is given; the pair is always written together.
"""
from __future__ import annotations

import argparse
import base64
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

ROOT = Path(__file__).resolve().parents[1]


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def generate() -> tuple[str, str]:
    """(public key, private key), both base64url without padding: the public key is the uncompressed point the
    browser's applicationServerKey expects, the private key the raw 32-byte scalar pywebpush accepts."""
    key = ec.generate_private_key(ec.SECP256R1())
    public = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return _b64(public), _b64(key.private_numbers().private_value.to_bytes(32, "big"))


def _read(env: Path) -> tuple[list[str], dict[str, str]]:
    lines = env.read_text(encoding="utf-8").splitlines() if env.exists() else []
    values = {}
    for ln in lines:
        if "=" in ln and not ln.lstrip().startswith("#"):
            k, _, v = ln.partition("=")
            values[k.strip()] = v.strip()
    return lines, values


def write_env(env: Path, public: str, private: str, subject: str, force: bool = False) -> bool:
    """Write the VAPID pair into an env file, preserving other lines. Returns True if the file was changed.

    The public and private key are always written together (a public key from one pair next to the private key of
    another makes every push fail with 403). Empty values count as missing. A complete existing pair is kept unless `force`."""
    lines, values = _read(env)
    have_pair = bool(values.get("VAPID_PUBLIC_KEY")) and bool(values.get("VAPID_PRIVATE_KEY"))
    if have_pair and not force:
        return False
    new = {"VAPID_PUBLIC_KEY": public, "VAPID_PRIVATE_KEY": private}
    if force or not values.get("VAPID_SUBJECT"):
        new["VAPID_SUBJECT"] = subject
    lines = [ln for ln in lines if ln.split("=", 1)[0].strip() not in new or ln.lstrip().startswith("#")]
    lines += [f"{k}={v}" for k, v in new.items()]
    env.write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
    try:
        os.chmod(env, 0o600)      # holds the private key; no-op semantics on Windows
    except OSError:
        pass
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--subject", default="mailto:admin@floodready.local")
    parser.add_argument("--env", type=Path, default=ROOT / ".env")
    parser.add_argument("--force", action="store_true", help="replace existing VAPID_* values")
    args = parser.parse_args()
    if not args.subject.startswith(("mailto:", "https://")):
        parser.error("--subject must start with mailto: or https://")
    public, private = generate()
    changed = write_env(args.env, public, private, args.subject, args.force)
    print(f"Wrote a new VAPID key pair to {args.env}" if changed else f"{args.env} already has a VAPID key pair; use --force to replace it")


if __name__ == "__main__":
    main()
