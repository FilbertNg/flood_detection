"""Link every street to the river station it drains to and the rain gauges around it (WP5, improvement #3).

Usage: python scripts/build_street_stations.py --township BBR
Writes assets/geo/<township>_street_stations.json:
  {street_id: {"wl": graph_id | null, "rf": [graph_id, ...], "method": "flow" | "nearest" | null, "distance_m": float | null}}

River station: trace the D8 flow path from the street's midpoint (floodready/gis/flow.py); the first township
river station on it within 15 km. If the path reaches none (flat coastal ground breaks D8), the nearest township
river station within `street_stations.river_radius_km` (config/rules.yaml). Otherwise null. Rain gauges: the township's gauges
within `rain_radius_km` of the midpoint, else the nearest `min_rain_gauges`.
Needs: data/raw/dem (Copernicus tile), data/interim/stations.parquet, assets/geo/<township>_streets.geojson.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import geopandas as gpd
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from floodready.engine import street_stations as ss  # noqa: E402
from floodready.gis import flow, terrain  # noqa: E402

DEM_NAME = "Copernicus_DSM_COG_10_N03_00_E101_00_DEM.tif"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--township", default="BBR")
    parser.add_argument("--buffer", type=int, default=15_000, help="DEM clip half-width around the township centre (m)")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data",
                        help="folder holding raw/dem and interim/stations.parquet (default <repo>/data)")
    parser.add_argument("--clip-dir", type=Path, default=None, help="where the clipped DEM is cached (default <data-dir>/interim)")
    args = parser.parse_args()
    data = args.data_dir
    args.clip_dir = args.clip_dir or data / "interim"

    town = next(t for t in yaml.safe_load((ROOT / "config" / "townships.yaml").read_text(encoding="utf-8"))["townships"]
                if t["id"] == args.township)
    cfg = ss.DEFAULTS | yaml.safe_load((ROOT / "config" / "rules.yaml").read_text(encoding="utf-8")).get("street_stations", {})
    lookup = pd.read_parquet(data / "interim" / "stations.parquet")
    ids = {s["graph_id"]: s.get("types", []) for s in town["stations"]}

    def located(kind: str) -> list[tuple[str, float, float]]:
        rows = lookup[(lookup.kind == kind) & lookup.graph_id.isin(ids)].drop_duplicates("graph_id")
        return [(r.graph_id, float(r.lat), float(r.lon)) for r in rows.itertuples() if pd.notna(r.lat)]

    wl, rf = located("wl"), located("rf")
    print(f"{args.township}: {len(wl)} river stations {[g for g, *_ in wl]}, {len(rf)} rain gauges")

    clip = terrain.clip_dem(data / "raw" / "dem" / DEM_NAME, args.clip_dir / f"dem_{args.township.lower()}_flow.tif",
                            town["centre"]["lat"], town["centre"]["lon"], args.buffer)
    grid = flow.flow_grid(clip)

    streets = gpd.read_file(ROOT / "assets" / "geo" / f"{args.township.lower()}_streets.geojson")
    out, spread = {}, {km: Counter() for km in (5, 8, 10, 12)}
    for street in streets.itertuples():
        mid = street.geometry.interpolate(0.5, normalized=True)
        lat, lon = mid.y, mid.x
        for km in spread:
            spread[km][sum(ss.distance_m(lat, lon, glat, glon) <= km * 1000 for _, glat, glon in rf)] += 1
        hits = flow.stations_downstream(grid, lat, lon, wl) if wl else []
        candidates = ss.pick_wl_candidates(hits, wl, lat, lon, cfg)
        wl_id, method, dist = candidates[0] if candidates else (None, None, None)
        out[street.street_id] = {"wl": wl_id, "wl_candidates": [c[0] for c in candidates],
                                 "rf": ss.rain_gauges(lat, lon, rf, cfg), "method": method, "distance_m": dist}

    path = ROOT / "assets" / "geo" / f"{args.township.lower()}_street_stations.json"
    path.write_text(json.dumps(out, indent=0, sort_keys=True), encoding="utf-8")

    print(f"{len(out)} streets -> {path.relative_to(ROOT)}")
    print("streets per river station:", dict(Counter(v["wl"] for v in out.values())))
    print("river candidates per street:", dict(sorted(Counter(len(v["wl_candidates"]) for v in out.values()).items())))
    print("streets per method:", dict(Counter(v["method"] for v in out.values())))
    print("streets with no river station:", sum(v["wl"] is None for v in out.values()))
    print("rain gauges per street (count: streets) by radius:", {f"{km} km": dict(sorted(c.items())) for km, c in spread.items()})
    print("streets per rain-gauge set:", dict(Counter(tuple(v["rf"]) for v in out.values()).most_common(10)))


if __name__ == "__main__":
    main()
