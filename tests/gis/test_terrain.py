import numpy as np
import geopandas as gpd
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import LineString

from floodready.gis import terrain

CELL_DEG = 0.0003  # ~33 m


def valley_dem(tmp_path, n=41):
    """A valley running north-south down the middle, sloping gently to the south."""
    x = np.abs(np.arange(n) - n // 2)               # distance from the valley line
    rows = np.arange(n)[:, None]
    dem = (5.0 + 0.8 * x[None, :] + 0.05 * (n - rows)).astype("float32")
    path = tmp_path / "dem.tif"
    transform = from_origin(101.40, 3.10, CELL_DEG, CELL_DEG)
    with rasterio.open(path, "w", driver="GTiff", height=n, width=n, count=1, dtype="float32",
                       crs="EPSG:4326", transform=transform) as dst:
        dst.write(dem, 1)
    return path, transform, n


def test_valley_floor_is_most_susceptible_and_ridges_least(tmp_path):
    path, _, n = valley_dem(tmp_path)
    result = terrain.terrain_indices(path, stream_threshold=20)
    index = result["index"]
    mid = n // 2
    inner = slice(5, n - 5)                         # ignore raster edges
    assert np.nanmedian(index[inner, mid]) == 5
    assert np.nanmedian(index[inner, 1]) == 1 and np.nanmedian(index[inner, n - 2]) == 1
    assert np.nanmin(result["hand"][inner, mid]) < np.nanmin(result["hand"][inner, 1])
    assert set(np.unique(index[~np.isnan(index)])) <= {1, 2, 3, 4, 5}


def test_streets_take_their_susceptibility_from_the_cells_they_cross(tmp_path):
    path, transform, n = valley_dem(tmp_path)
    result = terrain.terrain_indices(path, stream_threshold=20)
    lon_mid = 101.40 + (n // 2 + 0.5) * CELL_DEG
    lon_ridge = 101.40 + 1.5 * CELL_DEG
    lat_top, lat_bottom = 3.10 - 8 * CELL_DEG, 3.10 - (n - 8) * CELL_DEG
    streets = gpd.GeoDataFrame(
        {"street_id": ["X-valley", "X-ridge"]},
        geometry=[LineString([(lon_mid, lat_top), (lon_mid, lat_bottom)]),
                  LineString([(lon_ridge, lat_top), (lon_ridge, lat_bottom)])],
        crs=4326)
    scored = terrain.street_susceptibility(streets, result)
    valley = scored.set_index("street_id").loc["X-valley"]
    ridge = scored.set_index("street_id").loc["X-ridge"]
    assert valley.susceptibility == 5 and ridge.susceptibility <= 2
    assert valley.hand_m_min < ridge.hand_m_min
    assert scored.susceptibility.between(1, 5).all()


def test_streets_are_ranked_within_the_township_in_fifths(tmp_path):
    """Classes are relative to the township's own streets: each class holds about 20%."""
    path, _, n = valley_dem(tmp_path)
    result = terrain.terrain_indices(path, stream_threshold=20)
    lat_top, lat_bottom = 3.10 - 8 * CELL_DEG, 3.10 - (n - 8) * CELL_DEG
    cols = range(2, n - 2, 4)
    streets = gpd.GeoDataFrame(
        {"street_id": [f"X-{c}" for c in cols]},
        geometry=[LineString([(101.40 + (c + 0.5) * CELL_DEG, lat_top), (101.40 + (c + 0.5) * CELL_DEG, lat_bottom)]) for c in cols],
        crs=4326)
    scored = terrain.street_susceptibility(streets, result)
    counts = scored.susceptibility.value_counts()
    assert set(counts.index) == {1, 2, 3, 4, 5}
    assert counts.max() - counts.min() <= 1
    assert "score_mean" in scored.columns
