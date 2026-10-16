"""Fetch the open inputs for the extra street features (improvement #11).

1. ESA WorldCover 2021 v200 tile N03E099 (covers 3-6 N, 99-102 E; ~26 MB; CC BY 4.0)
   -> data/raw/worldcover/ESA_WorldCover_10m_2021_v200_N03E099_Map.tif
2. OSM waterways (river, stream, canal, drain, ditch) around the township as small
   Overpass tiles, cached like the street tiles -> data/raw/osm/<TOWNSHIP>_waterways_r<radius>/

Usage: python scripts/fetch_terrain_inputs.py --township BBR [--radius 5000]
Data: ESA WorldCover 2021 (c) ESA, CC BY 4.0; (c) OpenStreetMap contributors (ODbL).
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
sys.path.insert(0, str(ROOT / "scripts"))

from build_streets import fetch_tile  # noqa: E402
from floodready import storage  # noqa: E402
from floodready.gis import features, streets  # noqa: E402
from floodready.http import make_session  # noqa: E402

WORLDCOVER = "ESA_WorldCover_10m_2021_v200_N03E099_Map.tif"
WORLDCOVER_URL = f"https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/{WORLDCOVER}"


def fetch_worldcover(session) -> Path:
    dest = ROOT / "data" / "raw" / "worldcover" / WORLDCOVER
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    with session.get(WORLDCOVER_URL, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(tmp, "wb") as out:
            for chunk in r.iter_content(1 << 20):
                out.write(chunk)
    tmp.replace(dest)
    return dest


def fetch_waterways(session, town: dict, radius: int, tiles: int = 4) -> list[dict]:
    cache = ROOT / "data" / "raw" / "osm" / f"{town['id']}_waterways_r{radius}"
    payloads, missing = [], []
    for k, bbox in enumerate(streets.tile_bboxes(town["centre"]["lat"], town["centre"]["lon"], radius, tiles)):
        path = cache / f"tile_{k:02d}.json.gz"
        if path.exists():
            payloads.append(json.loads(storage.read_raw(path)))
            continue
        payload = fetch_tile(session, features.overpass_waterway_query(bbox))
        if payload is None:
            missing.append(k)
            continue
        storage.save_raw(path, json.dumps(payload))
        payloads.append(payload)
        time.sleep(3)
    if missing:
        sys.exit(f"waterway tiles {missing} failed; run again later (fetched tiles are cached)")
    return payloads


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--township", default="BBR")
    parser.add_argument("--radius", type=int, default=5000)
    args = parser.parse_args()
    town = next(t for t in yaml.safe_load((ROOT / "config" / "townships.yaml").read_text(encoding="utf-8"))["townships"]
                if t["id"] == args.township)
    session = make_session()
    print("WorldCover:", fetch_worldcover(session))
    payloads = fetch_waterways(session, town, args.radius)
    water = features.waterways_from_overpass(streets.merge_payloads(payloads))
    print(f"{len(water)} waterway segments;", water.waterway.value_counts().to_dict())


if __name__ == "__main__":
    main()
