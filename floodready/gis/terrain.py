"""Susceptibility baseline from terrain (build plan task G2).

HAND (height above nearest drainage) and TWI (topographic wetness index) from a
DEM, combined into a 1-5 index by quintiles: low HAND + high TWI = 5. Uses no
flood labels, so checking it against known flood streets is a fair test.
"""
from __future__ import annotations

import math
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.transform import rowcol
from rasterio.windows import from_bounds

if not hasattr(np, "in1d"):  # removed in NumPy 2.4; pysheds 0.5 only calls it on 1-D arrays
    np.in1d = np.isin

from pysheds.grid import Grid  # noqa: E402

M_PER_DEG = 111_320


def clip_dem(src: Path, dst: Path, lat: float, lon: float, buffer_m: float) -> Path:
    """Write the square of +-buffer_m around (lat, lon) to a new GeoTIFF."""
    dlat = buffer_m / M_PER_DEG
    dlon = buffer_m / (M_PER_DEG * math.cos(math.radians(lat)))
    with rasterio.open(src) as raster:
        window = from_bounds(lon - dlon, lat - dlat, lon + dlon, lat + dlat, raster.transform).round_offsets().round_lengths()
        data = raster.read(1, window=window)
        profile = raster.profile | {"height": data.shape[0], "width": data.shape[1],
                                    "transform": raster.window_transform(window), "driver": "GTiff"}
        profile.pop("blockxsize", None), profile.pop("blockysize", None), profile.pop("tiled", None)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(dst, "w", **profile) as out:
        out.write(data, 1)
    return dst


def _percentile_rank(values: np.ndarray) -> np.ndarray:
    flat = values.ravel()
    ok = ~np.isnan(flat)
    ranks = np.full(flat.shape, np.nan)
    order = flat[ok].argsort(kind="stable")
    r = np.empty(order.size)
    r[order] = np.arange(order.size)
    ranks[ok] = r / max(order.size - 1, 1)
    return ranks.reshape(values.shape)


def terrain_indices(dem_path: Path, stream_threshold: int = 200) -> dict:
    """HAND, TWI, flow accumulation and the 1-5 index for every DEM cell."""
    grid = Grid.from_raster(str(dem_path))
    dem = grid.read_raster(str(dem_path))
    conditioned = grid.resolve_flats(grid.fill_depressions(grid.fill_pits(dem)))
    fdir = grid.flowdir(conditioned)
    acc_raster = grid.accumulation(fdir)
    hand = np.asarray(grid.compute_hand(fdir, conditioned, acc_raster > stream_threshold), dtype="float64")
    acc = np.asarray(acc_raster, dtype="float64")

    with rasterio.open(dem_path) as raster:
        transform, crs = raster.transform, raster.crs
        elevation = raster.read(1).astype("float64")
        nodata = raster.nodata
    lat = transform.f + transform.e * elevation.shape[0] / 2
    cell_x = abs(transform.a) * M_PER_DEG * math.cos(math.radians(lat))
    cell_y = abs(transform.e) * M_PER_DEG
    if nodata is not None:
        elevation[elevation == nodata] = np.nan
    gy, gx = np.gradient(elevation, cell_y, cell_x)
    slope = np.arctan(np.hypot(gx, gy))
    twi = np.log((acc + 1) * cell_x / np.tan(np.maximum(slope, 0.001)))
    hand[~np.isfinite(hand)] = np.nan

    score = _percentile_rank(-hand) + _percentile_rank(twi)
    rank = _percentile_rank(score)
    index = np.where(np.isnan(rank), np.nan, np.minimum(1 + np.floor(rank * 5), 5))
    return {"hand": hand, "twi": twi, "acc": acc, "score": score, "index": index, "transform": transform, "crs": crs}


def _sample(line, result, step_m: float = 10.0) -> tuple[list, list, list]:
    """Combined terrain score, HAND and TWI at points every step_m along a line."""
    transform, score, hand, twi = result["transform"], result["score"], result["hand"], result["twi"]
    n = max(int(line.length * M_PER_DEG / step_m), 1)
    score_vals, hand_vals, twi_vals = [], [], []
    for k in range(n + 1):
        point = line.interpolate(k / n, normalized=True)
        r, c = rowcol(transform, point.x, point.y, op=math.floor)
        if 0 <= r < score.shape[0] and 0 <= c < score.shape[1] and not np.isnan(score[r, c]):
            score_vals.append(score[r, c]); hand_vals.append(hand[r, c]); twi_vals.append(twi[r, c])
    return score_vals, hand_vals, twi_vals


def street_susceptibility(streets: gpd.GeoDataFrame, result: dict) -> gpd.GeoDataFrame:
    """1-5 per street, ranked WITHIN the given streets (each class ~20%).

    The cell index is relative to the whole DEM clip (hills included), where a
    low-lying township lands almost entirely in the top classes; SDP needs to
    know which of its own streets are most flood-prone, so streets are ranked
    by their mean terrain score and split into fifths.
    """
    lines = streets.to_crs(result["crs"])
    score_mean, hand_min, twi_max = [], [], []
    for geom in lines.geometry:
        parts = list(geom.geoms) if geom.geom_type == "MultiLineString" else [geom]
        score_vals, hand_vals, twi_vals = [], [], []
        for part in parts:
            a, b, c = _sample(part, result)
            score_vals += a; hand_vals += b; twi_vals += c
        score_mean.append(float(np.mean(score_vals)) if score_vals else np.nan)
        hand_min.append(round(float(np.nanmin(hand_vals)), 2) if hand_vals else None)
        twi_max.append(round(float(np.nanmax(twi_vals)), 2) if twi_vals else None)
    out = streets.copy()
    out["score_mean"] = np.round(score_mean, 4)
    rank = out["score_mean"].rank(method="first")
    pct = (rank - 1) / max(rank.count() - 1, 1)
    out["susceptibility"] = np.where(pct.isna(), 3, np.minimum(1 + np.floor(pct * 5), 5)).astype(int)
    out["hand_m_min"], out["twi_max"] = hand_min, twi_max
    return out
