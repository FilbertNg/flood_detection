"""Fetch the FABDEM tile covering the townships (N03E101) from the University of Bristol.

FABDEM V1-2 (Hawker et al. 2022): Copernicus GLO-30 with building and forest
bias removed. Licence CC BY-NC-SA 4.0 (non-commercial: fine for a hackathon
prototype; SDP needs the authors' permission for commercial use).
Bristol only serves 10 x 10 degree zips (~556 MB); the server supports HTTP
range requests, so this reads the zip directory and downloads just one tile.

Usage: python scripts/fetch_fabdem.py [--tile N03E101]
"""
from __future__ import annotations

import argparse
import io
import re
import sys
import zipfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://data.bris.ac.uk/datasets/s5hqmjcdj8yo2ibzi9b4ew3sn"
OUT_DIR = ROOT / "data" / "raw" / "dem"


def zip_name(tile: str) -> str:
    """Name of the 10x10 degree zip that holds a 1x1 tile, e.g. N03E101 -> N00E100-N10E110_FABDEM_V1-2.zip."""
    m = re.fullmatch(r"([NS])(\d{2})([EW])(\d{3})", tile)
    if not m:
        raise ValueError(f"bad tile name {tile!r}")
    ns, lat, ew, lon = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
    if ns == "N" and ew == "E":
        lat0, lon0 = lat // 10 * 10, lon // 10 * 10
        return f"N{lat0:02d}E{lon0:03d}-N{lat0 + 10:02d}E{lon0 + 10:03d}_FABDEM_V1-2.zip"
    raise ValueError("only N/E tiles are needed for Malaysia")


class RangeFile(io.RawIOBase):
    """Read-only seekable file over HTTP range requests, enough for zipfile."""

    def __init__(self, url: str):
        self.url, self.pos = url, 0
        head = requests.head(url, allow_redirects=True, timeout=60)
        head.raise_for_status()
        if head.headers.get("Accept-Ranges") != "bytes":
            raise RuntimeError("server does not support range requests")
        self.size = int(head.headers["Content-Length"])

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = {0: offset, 1: self.pos + offset, 2: self.size + offset}[whence]
        return self.pos

    def read(self, n=-1):
        end = self.size if n is None or n < 0 else min(self.pos + n, self.size)
        if self.pos >= end:
            return b""
        r = requests.get(self.url, headers={"Range": f"bytes={self.pos}-{end - 1}"}, timeout=120)
        r.raise_for_status()
        self.pos += len(r.content)
        return r.content

    def readinto(self, b):
        data = self.read(len(b))
        b[:len(data)] = data
        return len(data)


def check_tile(path: Path) -> dict:
    """Open with rasterio and sanity-check CRS, bounds and elevations."""
    import numpy as np
    import rasterio
    with rasterio.open(path) as r:
        a = r.read(1, masked=True)
        info = {"crs": str(r.crs), "bounds": tuple(round(v, 4) for v in r.bounds), "shape": r.shape,
                "min": float(a.min()), "max": float(a.max()), "mean": float(a.mean())}
    assert info["crs"] == "EPSG:4326", info
    assert -100 < info["min"] and info["max"] < 3000, info
    assert np.isfinite(info["mean"])
    return info


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tile", default="N03E101")
    args = parser.parse_args()
    dest = OUT_DIR / f"{args.tile}_FABDEM_V1-2.tif"
    if dest.exists():
        print(f"{dest} exists; checking only")
    else:
        url = f"{BASE}/{zip_name(args.tile)}"
        with zipfile.ZipFile(RangeFile(url)) as z:
            member = next((n for n in z.namelist() if n.endswith(f"{args.tile}_FABDEM_V1-2.tif")), None)
            if member is None:
                sys.exit(f"{args.tile} not in {url}")
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_suffix(".part")
            with z.open(member) as src, open(tmp, "wb") as out:
                while chunk := src.read(1 << 20):
                    out.write(chunk)
            tmp.replace(dest)
    print(dest, check_tile(dest))
    print("FABDEM V1-2 (c) University of Bristol (Hawker et al. 2022), CC BY-NC-SA 4.0")


if __name__ == "__main__":
    main()
