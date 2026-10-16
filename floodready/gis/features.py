"""Extra street features for the terrain susceptibility score (improvement #11).

All open data, no flood labels: distance to the nearest OSM waterway, slope,
built-up share within 100 m (ESA WorldCover class 50), plus HAND and TWI from
terrain.py. Streets are ranked on each feature and the ranks averaged with equal
weights; nothing is fitted to the memorandum streets.
Data: (c) OpenStreetMap contributors (ODbL); ESA WorldCover 2021 (CC BY 4.0).
"""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
from rasterio.features import geometry_mask
from shapely.geometry import LineString
from shapely.ops import unary_union

METRIC_CRS = 32647  # UTM 47N, same as streets.py
WATERWAYS = ("river", "stream", "canal", "drain", "ditch")
BUILT_UP = 50  # ESA WorldCover class "Built-up"

# Feature -> +1 if a higher value means MORE flood-prone, -1 if lower does.
DIRECTION = {
    "hand": -1,     # low height above the nearest drainage
    "twi": +1,      # water collects where the wetness index is high
    "water_m": -1,  # close to a river or drain
    "slope": -1,    # flat ground drains slowly
    "built": +1,    # impervious surface sheds more runoff
}


def overpass_waterway_query(bbox: tuple[float, float, float, float]) -> str:
    s, w, n, e = bbox
    return (f'[out:json][timeout:60];\n'
            f'way({s:.5f},{w:.5f},{n:.5f},{e:.5f})["waterway"~"^({"|".join(WATERWAYS)})$"];\n'
            f'out geom;')


def waterways_from_overpass(payload: dict) -> gpd.GeoDataFrame:
    rows = []
    for el in payload.get("elements", []):
        tags = el.get("tags", {})
        if el.get("type") != "way" or tags.get("waterway") not in WATERWAYS or len(el.get("geometry", [])) < 2:
            continue
        rows.append({"osm_id": el["id"], "waterway": tags["waterway"], "name": tags.get("name"),
                     "geometry": LineString([(p["lon"], p["lat"]) for p in el["geometry"]])})
    return gpd.GeoDataFrame(rows, columns=["osm_id", "waterway", "name", "geometry"], geometry="geometry", crs=4326)


def slope_degrees(elevation: np.ndarray, cell_x: float, cell_y: float) -> np.ndarray:
    gy, gx = np.gradient(elevation, cell_y, cell_x)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def _sample_points(line, step_m: float = 10.0):
    n = max(int(line.length / step_m), 1)
    return [line.interpolate(k / n, normalized=True) for k in range(n + 1)]


def distance_to_waterways(lines: gpd.GeoSeries, waterways: gpd.GeoSeries) -> np.ndarray:
    """Mean distance in metres from points along each street to the nearest waterway (NaN if none)."""
    if len(waterways) == 0:
        return np.full(len(lines), np.nan)
    water = unary_union(list(waterways.to_crs(METRIC_CRS).geometry))
    out = []
    for geom in lines.to_crs(METRIC_CRS).geometry:
        parts = list(geom.geoms) if geom.geom_type == "MultiLineString" else [geom]
        d = [p.distance(water) for part in parts for p in _sample_points(part)]
        out.append(float(np.mean(d)))
    return np.array(out)


def built_up_share(lines: gpd.GeoSeries, landcover: np.ndarray, transform, crs, buffer_m: float = 100.0) -> np.ndarray:
    """Share of land-cover cells within buffer_m of each street that are Built-up (class 50)."""
    built = landcover == BUILT_UP
    metric = lines.set_crs(crs, allow_override=False) if lines.crs is None else lines
    buffers = gpd.GeoSeries(metric.to_crs(METRIC_CRS).buffer(buffer_m), crs=METRIC_CRS).to_crs(crs)
    out = []
    for poly in buffers:
        inside = geometry_mask([poly], out_shape=built.shape, transform=transform, invert=True)
        out.append(float(built[inside].mean()) if inside.any() else np.nan)
    return np.array(out)


def combine_ranks(table: pd.DataFrame, direction: dict[str, int] = DIRECTION) -> pd.Series:
    """Equal-weight mean of percentile ranks (0 = least, 1 = most flood-prone) over the available features."""
    ranks = []
    for col, sign in direction.items():
        if col in table and table[col].notna().any():
            values = table[col] * sign
            ranks.append((values.rank(method="average") - 1) / max(values.count() - 1, 1))
    if not ranks:
        return pd.Series(np.nan, index=table.index)
    return pd.concat(ranks, axis=1).mean(axis=1)


def fifths(score: pd.Series) -> pd.Series:
    """1-5 classes of equal size by rank within the given streets; unscored streets get 3."""
    rank = score.rank(method="first")
    pct = (rank - 1) / max(rank.count() - 1, 1)
    return pd.Series(np.where(pct.isna(), 3, np.minimum(1 + np.floor(pct * 5), 5)).astype(int), index=score.index)
