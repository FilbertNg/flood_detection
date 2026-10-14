"""G1: named streets for a township from OpenStreetMap → assets/geo/<township>_streets.geojson.

Fetches the square around the township centre as small Overpass tiles (large
queries get refused), caches each tile, retries with backoff, and merges.

Usage:
  python scripts/build_streets.py --township BBR            # 3 km around the centre in config/townships.yaml
  python scripts/build_streets.py --township BBR --radius 4000
Data © OpenStreetMap contributors (ODbL).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from floodready import storage  # noqa: E402
from floodready.gis import streets  # noqa: E402
from floodready.http import make_session  # noqa: E402

MEMORANDUM = ("Jalan Makyong", "Jalan Sumazau", "Persiaran Sungai Keramat", "Persiaran Batu Belah")


def fetch_tile(session, query: str) -> dict | None:
    """Main server first with short retries (504 = busy, usually clears in seconds);
    the mirrors are slower, so they are the last resort."""
    main, *mirrors = streets.OVERPASS_URLS
    for attempt in range(8):
        try:
            response = session.post(main, data={"data": query}, timeout=90)
            if response.status_code == 200:
                return json.loads(response.text)
        except Exception:
            pass
        time.sleep(4 + 4 * attempt)
    for url in mirrors:
        try:
            response = session.post(url, data={"data": query}, timeout=60)
            if response.status_code == 200:
                return json.loads(response.text)
        except Exception:
            pass
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--township", default="BBR")
    parser.add_argument("--radius", type=int, default=3000)
    parser.add_argument("--tiles", type=int, default=4, help="n x n tiles")
    args = parser.parse_args()

    townships = yaml.safe_load((ROOT / "config" / "townships.yaml").read_text(encoding="utf-8"))["townships"]
    town = next(t for t in townships if t["id"] == args.township)
    cache = ROOT / "data" / "raw" / "osm" / f"{args.township}_r{args.radius}"
    session, payloads, missing = make_session(), [], []
    for k, bbox in enumerate(streets.tile_bboxes(town["centre"]["lat"], town["centre"]["lon"], args.radius, args.tiles)):
        path = cache / f"tile_{k:02d}.json.gz"
        if path.exists():
            payloads.append(json.loads(storage.read_raw(path)))
            continue
        payload = fetch_tile(session, streets.overpass_bbox_query(bbox))
        if payload is None:
            missing.append(k)
            continue
        storage.save_raw(path, json.dumps(payload))
        payloads.append(payload)
        time.sleep(2)
    if missing:
        sys.exit(f"tiles {missing} failed after retries; run again later (fetched tiles are cached)")

    gdf = streets.streets_from_overpass(streets.merge_payloads(payloads), township_id=args.township)
    out = ROOT / "assets" / "geo" / f"{args.township.lower()}_streets.geojson"
    out.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(out, driver="GeoJSON")
    print(f"{len(gdf)} named streets, {gdf.length_m.sum() / 1000:.1f} km → {out.relative_to(ROOT)}")
    for prefix in MEMORANDUM:
        hits = gdf[gdf.name.str.startswith(prefix)]
        print(f"  {prefix}: {len(hits)} street(s) {list(hits.street_id)[:6]}")


if __name__ == "__main__":
    main()
