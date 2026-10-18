"""Generate a VAPID key pair for Web Push and write it to .env (gitignored). Never commit the keys.

python scripts/gen_vapid.py [--subject mailto:you@example.com] [--env .env] [--force]

Existing VAPID_* lines are kept unless --force is given.
"""
from __future__ import annotations

import argparse
import base64
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


def write_env(env: Path, values: dict[str, str], force: bool = False) -> list[str]:
    """Set the keys in an env file, preserving other lines. Returns the names written."""
    lines = env.read_text(encoding="utf-8").splitlines() if env.exists() else []
    present = {ln.split("=", 1)[0].strip() for ln in lines if "=" in ln and not ln.lstrip().startswith("#")}
    written = []
    for name, value in values.items():
        if name in present and not force:
            continue
        lines = [ln for ln in lines if ln.split("=", 1)[0].strip() != name]
        lines.append(f"{name}={value}")
        written.append(name)
    env.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--subject", default="mailto:admin@floodready.local")
    parser.add_argument("--env", type=Path, default=ROOT / ".env")
    parser.add_argument("--force", action="store_true", help="replace existing VAPID_* values")
    args = parser.parse_args()
    if not args.subject.startswith(("mailto:", "https://")):
        parser.error("--subject must start with mailto: or https://")
    public, private = generate()
    written = write_env(args.env, {"VAPID_PUBLIC_KEY": public, "VAPID_PRIVATE_KEY": private, "VAPID_SUBJECT": args.subject}, args.force)
    print(f"Wrote {', '.join(written) or 'nothing (keys already present; use --force)'} to {args.env}")


if __name__ == "__main__":
    main()
