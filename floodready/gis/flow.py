"""Flow paths on a DEM: where water from a point goes, and which river stations it passes.

Used to link streets to the river station they drain to, and river stations to
the stations upstream of them. D8 flow directions from pysheds (default dirmap).
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import rowcol

from .terrain import M_PER_DEG, Grid

# pysheds default dirmap (N, NE, E, SE, S, SW, W, NW) -> (row step, col step)
D8 = {64: (-1, 0), 128: (-1, 1), 1: (0, 1), 2: (1, 1), 4: (1, 0), 8: (1, -1), 16: (0, -1), 32: (-1, -1)}


def flow_grid(dem_path: Path) -> dict:
    """Flow direction and accumulation for every cell, plus the georeferencing needed to walk them."""
    grid = Grid.from_raster(str(dem_path))
    dem = grid.read_raster(str(dem_path))
    fdir = grid.flowdir(grid.resolve_flats(grid.fill_depressions(grid.fill_pits(dem))))
    acc = grid.accumulation(fdir)
    with rasterio.open(dem_path) as raster:
        transform, shape = raster.transform, (raster.height, raster.width)
    lat = transform.f + transform.e * shape[0] / 2
    cell_m = (abs(transform.a) * M_PER_DEG * math.cos(math.radians(lat)) + abs(transform.e) * M_PER_DEG) / 2
    return {"fdir": np.asarray(fdir, dtype="int64"), "acc": np.asarray(acc, dtype="float64"),
            "transform": transform, "shape": shape, "cell_m": cell_m}


def cell_of(grid: dict, lat: float, lon: float) -> tuple[int, int] | None:
    r, c = rowcol(grid["transform"], lon, lat, op=math.floor)
    rows, cols = grid["shape"]
    return (int(r), int(c)) if 0 <= r < rows and 0 <= c < cols else None


def _disc(grid: dict, centre: tuple[int, int], radius_m: float) -> list[tuple[int, int]]:
    k = int(radius_m // grid["cell_m"])
    rows, cols = grid["shape"]
    r0, c0 = centre
    return [(r, c) for r in range(r0 - k, r0 + k + 1) for c in range(c0 - k, c0 + k + 1)
            if 0 <= r < rows and 0 <= c < cols and (r - r0) ** 2 + (c - c0) ** 2 <= k * k]


def snap_to_stream(grid: dict, lat: float, lon: float, radius_m: float = 150) -> tuple[int, int] | None:
    """The highest-accumulation cell within radius_m: a gauge sits on the river, the DEM's river may be offset."""
    centre = cell_of(grid, lat, lon)
    if centre is None:
        return None
    return max(_disc(grid, centre, radius_m), key=lambda rc: grid["acc"][rc])


def downstream_cells(grid: dict, lat: float, lon: float, start: tuple[int, int] | None = None,
                     max_steps: int = 50_000) -> list[tuple[int, int]]:
    """Cells water passes from (lat, lon), in order, until it leaves the DEM, reaches a sink or loops."""
    cell = start if start is not None else cell_of(grid, lat, lon)
    if cell is None:
        return []
    rows, cols = grid["shape"]
    path, seen = [cell], {cell}
    for _ in range(max_steps):
        step = D8.get(int(grid["fdir"][cell]))
        if step is None:
            break
        nxt = (cell[0] + step[0], cell[1] + step[1])
        if not (0 <= nxt[0] < rows and 0 <= nxt[1] < cols) or nxt in seen:
            break
        path.append(nxt)
        seen.add(nxt)
        cell = nxt
    return path


def _station_cells(grid: dict, stations: list[tuple[str, float, float]], snap_m: float) -> dict:
    """Cell -> station id for every cell within snap_m of each station's snapped river cell."""
    lookup = {}
    for sid, lat, lon in stations:
        snapped = snap_to_stream(grid, lat, lon, radius_m=snap_m)
        if snapped is not None:
            for rc in _disc(grid, snapped, snap_m):
                lookup.setdefault(rc, sid)
    return lookup


def stations_downstream(grid: dict, lat: float, lon: float, stations: list[tuple[str, float, float]],
                        snap_m: float = 300, start: tuple[int, int] | None = None,
                        exclude: str | None = None) -> list[tuple[str, float]]:
    """Stations on the flow path from (lat, lon), nearest first, with the distance along the path (m)."""
    lookup = _station_cells(grid, stations, snap_m)
    found, seen = [], {exclude}
    for i, rc in enumerate(downstream_cells(grid, lat, lon, start=start)):
        sid = lookup.get(rc)
        if sid is not None and sid not in seen:
            found.append((sid, round(i * grid["cell_m"], 1)))
            seen.add(sid)
    return found


def upstream_map(grid: dict, stations: list[tuple[str, float, float]], snap_m: float = 300) -> dict[str, list[str]]:
    """For each station, the stations whose water passes it (directly or further up the same river)."""
    up: dict[str, list[str]] = {sid: [] for sid, _, _ in stations}
    for sid, lat, lon in stations:
        start = snap_to_stream(grid, lat, lon, radius_m=snap_m)
        if start is None:
            continue
        for down, _ in stations_downstream(grid, lat, lon, stations, snap_m=snap_m, start=start, exclude=sid):
            up[down].append(sid)
    return {k: sorted(v) for k, v in up.items()}
