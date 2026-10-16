"""G2 / terrain v2: terrain susceptibility (no flood labels) for a township's streets.

Three variants are scored and compared on the held-out memorandum streets:
  glo30_old    Copernicus GLO-30 DEM, HAND + TWI score (the original map)
  fabdem_old   FABDEM DEM (buildings and forests removed), same score
  fabdem_new   FABDEM + distance to waterway, slope, built-up share within 100 m
               (equal-weight percentile ranks of HAND, TWI, waterway distance, slope, built-up)
fabdem_new is pre-specified (WP4 brief) and ships by default (--ship); it is written to
assets/geo/<township>_streets.geojson and the index raster to
data/interim/susceptibility_<township>_v2.tif. The memorandum numbers of all three
variants are printed as a report only: they confirm, they never select. The check
has only 4 named streets, so nothing is tuned to it.

Run first: scripts/fetch_fabdem.py, scripts/fetch_terrain_inputs.py
Usage: python scripts/build_susceptibility.py --township BBR [--ship glo30_old|fabdem_old|fabdem_new]
DEMs: Copernicus GLO-30 (DLR/Airbus, EU/ESA); FABDEM V1-2 (Univ. of Bristol, CC BY-NC-SA 4.0).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import yaml
from rasterio.warp import Resampling, reproject
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from floodready import storage  # noqa: E402
from floodready.gis import features, terrain  # noqa: E402

GLO30 = ROOT / "data" / "raw" / "dem" / "Copernicus_DSM_COG_10_N03_00_E101_00_DEM.tif"
FABDEM = ROOT / "data" / "raw" / "dem" / "N03E101_FABDEM_V1-2.tif"
WORLDCOVER = ROOT / "data" / "raw" / "worldcover" / "ESA_WorldCover_10m_2021_v200_N03E099_Map.tif"
MEMORANDUM = ("Jalan Makyong", "Jalan Sumazau", "Persiaran Sungai Keramat", "Persiaran Batu Belah")
DERIVED = ("susceptibility", "hand_m_min", "twi_max", "index_mean", "score_mean", "hand_m_mean", "twi_mean",
           "slope_deg_mean", "water_dist_m", "built_share_100m", "susceptibility_v1")


def evaluate(scored_class: pd.Series, score: pd.Series, memo: pd.Series) -> dict:
    return {"memo_segments": int(memo.sum()),
            "hit_rate_classes_4_5": round(float((scored_class[memo] >= 4).mean()), 3),
            "median_percentile": round(float(score.rank(pct=True)[memo].median()), 3),
            "memo_segments_per_class": {int(k): int(v) for k, v in scored_class[memo].value_counts().sort_index().items()}}


def load_waterways(township: str, radius: int) -> gpd.GeoDataFrame:
    payloads = [json.loads(storage.read_raw(p)) for p in sorted((ROOT / "data" / "raw" / "osm" / f"{township}_waterways_r{radius}").glob("tile_*.json.gz"))]
    from floodready.gis import streets as streets_mod
    return features.waterways_from_overpass(streets_mod.merge_payloads(payloads))


def read_worldcover(bounds: tuple[float, float, float, float]):
    with rasterio.open(WORLDCOVER) as src:
        window = from_bounds(*bounds, src.transform).round_offsets().round_lengths()
        return src.read(1, window=window), src.window_transform(window), src.crs


def dem_comparison(glo: Path, fab: Path) -> dict:
    """GLO-30 minus FABDEM on the shared clip, split by how built-up each 30 m cell is (WorldCover share)."""
    with rasterio.open(glo) as g, rasterio.open(fab) as f:
        a, b = g.read(1).astype("float64"), f.read(1).astype("float64")
        lc, lc_tr, lc_crs = read_worldcover(tuple(g.bounds))
        share = np.zeros(a.shape, dtype="float32")
        reproject((lc == features.BUILT_UP).astype("float32"), share, src_transform=lc_tr, src_crs=lc_crs,
                  dst_transform=g.transform, dst_crs=g.crs, resampling=Resampling.average)
    diff = a - b
    ok = np.isfinite(diff)

    def stats(mask):
        d = diff[ok & mask]
        return {"cells": int(d.size), "mean_m": round(float(d.mean()), 2), "median_m": round(float(np.median(d)), 2),
                "p95_m": round(float(np.percentile(d, 95)), 2)}
    return {"all": stats(np.ones_like(ok)), "built_up_over_50pct": stats(share > 0.5), "built_up_under_5pct": stats(share < 0.05),
            "fabdem_minus_glo_mean_m": round(float((b - a)[ok].mean()), 2)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--township", default="BBR")
    parser.add_argument("--buffer", type=int, default=8000, help="DEM clip half-width in metres")
    parser.add_argument("--stream-cells", type=int, default=500, help="flow accumulation that starts a stream")
    parser.add_argument("--water-radius", type=int, default=5000)
    parser.add_argument("--ship", choices=("glo30_old", "fabdem_old", "fabdem_new"), default="fabdem_new", help="variant to write (default: pre-specified fabdem_new)")
    args = parser.parse_args()

    town = next(t for t in yaml.safe_load((ROOT / "config" / "townships.yaml").read_text(encoding="utf-8"))["townships"]
                if t["id"] == args.township)
    tid = args.township.lower()
    lat, lon = town["centre"]["lat"], town["centre"]["lon"]
    interim = ROOT / "data" / "interim"
    clip_glo = terrain.clip_dem(GLO30, interim / f"dem_{tid}.tif", lat, lon, args.buffer)
    clip_fab = terrain.clip_dem(FABDEM, interim / f"dem_{tid}_fabdem.tif", lat, lon, args.buffer)
    res_glo = terrain.terrain_indices(clip_glo, stream_threshold=args.stream_cells)
    res_fab = terrain.terrain_indices(clip_fab, stream_threshold=args.stream_cells)

    streets_path = ROOT / "assets" / "geo" / f"{tid}_streets.geojson"
    base = gpd.read_file(streets_path)
    base = base[[c for c in base.columns if c not in DERIVED]]
    memo = base.name.str.startswith(MEMORANDUM)

    old_glo = terrain.street_susceptibility(base, res_glo)
    old_fab = terrain.street_susceptibility(base, res_fab)

    # new features, on the FABDEM terrain
    means = terrain.street_terrain_means(base, res_fab)
    water = load_waterways(args.township, args.water_radius)
    lc, lc_tr, lc_crs = read_worldcover((base.total_bounds[0] - 0.01, base.total_bounds[1] - 0.01,
                                         base.total_bounds[2] + 0.01, base.total_bounds[3] + 0.01))
    table = means.assign(water_m=features.distance_to_waterways(base.geometry, water.geometry),
                         built=features.built_up_share(base.geometry, lc, lc_tr, lc_crs))
    new_score = features.combine_ranks(table)
    new_class = features.fifths(new_score)

    results = {
        "glo30_old": evaluate(old_glo.susceptibility, old_glo.score_mean, memo),
        "fabdem_old": evaluate(old_fab.susceptibility, old_fab.score_mean, memo),
        "fabdem_new": evaluate(new_class, new_score, memo),
    }
    ablation = {}
    for col in features.DIRECTION:
        single = features.combine_ranks(table[[col]], {col: features.DIRECTION[col]})
        ablation[col] = evaluate(features.fifths(single), single, memo)
    results["_ablation_single_feature_fabdem"] = ablation
    loo = {}
    for col in features.DIRECTION:
        rest = {k: v for k, v in features.DIRECTION.items() if k != col}
        score = features.combine_ranks(table, rest)
        loo[f"drop_{col}"] = evaluate(features.fifths(score), score, memo)
    results["_leave_one_feature_out_fabdem"] = loo
    per_street = {}
    for label, cls in (("glo30_old", old_glo.susceptibility), ("fabdem_old", old_fab.susceptibility), ("fabdem_new", new_class)):
        per_street[label] = {}
        for prefix in MEMORANDUM:
            sel = base.name.str.startswith(prefix)
            if sel.any():
                per_street[label][prefix] = {"segments": int(sel.sum()), "hit_rate": round(float((cls[sel] >= 4).mean()), 3)}
    results["_per_street_hit_rate"] = per_street
    results["_dem_comparison_glo_minus_fabdem"] = dem_comparison(clip_glo, clip_fab)
    results["_inputs"] = {"streets": len(base), "waterway_segments": len(water), "memorandum_segments": int(memo.sum()),
                          "streets_with_water_distance": int(table.water_m.notna().sum())}
    print(json.dumps(results, indent=2))

    best = args.ship  # pre-specified, never chosen from the memorandum numbers
    print(f"shipping: {best}")

    out = old_glo.rename(columns={"susceptibility": "susceptibility_v1"})[["street_id", "susceptibility_v1"]]
    scored = base.merge(out, on="street_id")
    chosen = {"glo30_old": old_glo, "fabdem_old": old_fab}.get(best)
    if chosen is not None:
        scored["susceptibility"] = chosen.susceptibility.values
        scored["score_mean"] = chosen.score_mean.values
        scored["hand_m_min"], scored["twi_max"] = chosen.hand_m_min.values, chosen.twi_max.values
    else:
        scored["susceptibility"] = new_class.values
        scored["score_mean"] = new_score.round(4).values
        scored["hand_m_min"], scored["twi_max"] = old_fab.hand_m_min.values, old_fab.twi_max.values
    scored["hand_m_mean"], scored["twi_mean"] = means.hand.round(2).values, means.twi.round(2).values
    scored["slope_deg_mean"] = means.slope.round(2).values
    scored["water_dist_m"] = table.water_m.round(0).values
    scored["built_share_100m"] = table.built.round(3).values
    scored.to_file(streets_path, driver="GeoJSON")

    # index raster to a NEW file; cell-level index of the shipped DEM (the new features are per street)
    index_res = res_glo if best == "glo30_old" else res_fab
    index_path = interim / f"susceptibility_{tid}_v2.tif"
    with rasterio.open(clip_fab if best != "glo30_old" else clip_glo) as src:
        profile = src.profile | {"dtype": "float32", "nodata": np.nan}
    with rasterio.open(index_path, "w", **profile) as dst:
        dst.write(index_res["index"].astype("float32"), 1)
    print(f"{len(scored)} streets -> {streets_path.relative_to(ROOT)}; index raster -> {index_path.relative_to(ROOT)}")
    print(f"streets per class: {scored.susceptibility.value_counts().sort_index().to_dict()}")
    for prefix in MEMORANDUM:
        hits = scored[scored.name.str.startswith(prefix)]
        print(f"  {prefix}: classes {sorted(hits.susceptibility.tolist())}" if len(hits) else f"  {prefix}: not found")


if __name__ == "__main__":
    main()
