from floodready.gis import flow

from test_terrain import CELL_DEG, valley_dem  # tests/gis is on sys.path (pytest rootdir-relative import)

# valley_dem: both sides slope down to a north-south valley in the middle column,
# which itself slopes to the south, so all water ends up flowing south along it.


def _at(row, col):
    """Cell-centre (lat, lon) in the valley DEM."""
    return 3.10 - (row + 0.5) * CELL_DEG, 101.40 + (col + 0.5) * CELL_DEG


def _stations(n):
    mid = n // 2
    return [("TOP", *_at(8, mid)), ("BOTTOM", *_at(n - 12, mid))]


def test_water_from_the_slope_reaches_the_valley_station_below_it(tmp_path):
    path, _, n = valley_dem(tmp_path)
    grid = flow.flow_grid(path)
    found = flow.stations_downstream(grid, *_at(20, n // 2 + 8), _stations(n), snap_m=60)
    assert [sid for sid, _ in found] == ["BOTTOM"]           # enters the valley below TOP, flows south
    assert found[0][1] > 0                                     # distance along the path, in metres


def test_water_starting_below_the_last_station_reaches_none(tmp_path):
    path, _, n = valley_dem(tmp_path)
    grid = flow.flow_grid(path)
    assert flow.stations_downstream(grid, *_at(n - 5, n // 2 + 3), _stations(n), snap_m=60) == []


def test_upstream_map_links_stations_on_the_same_river(tmp_path):
    path, _, n = valley_dem(tmp_path)
    grid = flow.flow_grid(path)
    stations = _stations(n) + [("TAIL", *_at(n - 4, n // 2))]
    up = flow.upstream_map(grid, stations, snap_m=60)
    assert up == {"TOP": [], "BOTTOM": ["TOP"], "TAIL": ["BOTTOM", "TOP"]}


def test_points_outside_the_dem_have_no_path(tmp_path):
    path, _, _ = valley_dem(tmp_path)
    grid = flow.flow_grid(path)
    assert flow.downstream_cells(grid, 2.0, 100.0) == []
