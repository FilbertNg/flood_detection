"""G2: terrain susceptibility (HAND + TWI baseline, no flood labels) for a township's streets.

Clips the Copernicus GLO-30 DEM around the township, computes HAND, TWI and a
1-5 index per 30 m cell, scores every street and writes the scores back into
assets/geo/<township>_streets.geojson. Also writes the cell index as a GeoTIFF
for the map overlay, and prints where the memorandum streets fall.

Usage: python scripts/build_susceptibility.py --township BBR
DEM: Copernicus GLO-30 (© DLR/Airbus, provided under COPERNICUS by the EU and ESA).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from floodready.gis import terrain  # noqa: E402

DEM = ROOT / "data" / "raw" / "dem" / "Copernicus_DSM_COG_10_N03_00_E101_00_DEM.tif"
MEMORANDUM = ("Jalan Makyong", "Jalan Sumazau", "Persiaran Sungai Keramat", "Persiaran Batu Belah")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--township", default="BBR")
    parser.add_argument("--buffer", type=int, default=8000, help="DEM clip half-width in metres")
    parser.add_argument("--stream-cells", type=int, default=500, help="flow accumulation that starts a stream")
    args = parser.parse_args()

    town = next(t for t in yaml.safe_load((ROOT / "config" / "townships.yaml").read_text(encoding="utf-8"))["townships"]
                if t["id"] == args.township)
    clipped = terrain.clip_dem(DEM, ROOT / "data" / "interim" / f"dem_{args.township.lower()}.tif",
                               town["centre"]["lat"], town["centre"]["lon"], args.buffer)
    result = terrain.terrain_indices(clipped, stream_threshold=args.stream_cells)

    index_path = ROOT / "data" / "interim" / f"susceptibility_{args.township.lower()}.tif"
    with rasterio.open(clipped) as src:
        profile = src.profile | {"dtype": "float32", "nodata": np.nan}
    with rasterio.open(index_path, "w", **profile) as dst:
        dst.write(result["index"].astype("float32"), 1)

    streets_path = ROOT / "assets" / "geo" / f"{args.township.lower()}_streets.geojson"
    streets = gpd.read_file(streets_path)
    keep = [c for c in streets.columns if c not in ("susceptibility", "hand_m_min", "twi_max", "index_mean")]
    scored = terrain.street_susceptibility(streets[keep], result)
    scored.to_file(streets_path, driver="GeoJSON")

    counts = scored.susceptibility.value_counts().sort_index().to_dict()
    print(f"{len(scored)} streets scored → {streets_path.relative_to(ROOT)}; index raster → {index_path.relative_to(ROOT)}")
    print(f"streets per class (1 = least, 5 = most flood-prone): {counts}")
    print("Memorandum streets (NOT used to build the map — a fair out-of-sample check):")
    for prefix in MEMORANDUM:
        hits = scored[scored.name.str.startswith(prefix)]
        if len(hits):
            print(f"  {prefix}: classes {sorted(hits.susceptibility.tolist())}, min HAND {hits.hand_m_min.min()} m")
        else:
            print(f"  {prefix}: not found in OSM extract")
    share = (scored.susceptibility >= 4).mean()
    print(f"share of all streets in classes 4-5: {share:.0%} (the memorandum result only means something if this is well below 100%)")


if __name__ == "__main__":
    main()
