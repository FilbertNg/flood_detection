import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from rasterio.transform import from_origin
from shapely.geometry import LineString

from floodready.gis import features

CELL_DEG = 0.0003


def test_overpass_waterway_query_lists_all_classes():
    q = features.overpass_waterway_query((3.0, 101.0, 3.1, 101.1))
    for w in ("river", "stream", "canal", "drain", "ditch"):
        assert w in q
    assert "3.00000,101.00000,3.10000,101.10000" in q


def test_waterways_from_payload_keeps_lines_and_drops_other_types():
    payload = {"elements": [
        {"type": "way", "id": 1, "tags": {"waterway": "drain"}, "geometry": [{"lon": 101.0, "lat": 3.0}, {"lon": 101.001, "lat": 3.0}]},
        {"type": "way", "id": 2, "tags": {"waterway": "dam"}, "geometry": [{"lon": 101.0, "lat": 3.0}, {"lon": 101.001, "lat": 3.0}]},
        {"type": "node", "id": 3, "tags": {"waterway": "river"}},
    ]}
    gdf = features.waterways_from_overpass(payload)
    assert len(gdf) == 1 and gdf.crs.to_epsg() == 4326


def test_slope_of_a_plane():
    # 1 m rise per 30 m cell eastwards -> atan(1/30) ~ 1.9 degrees
    x = np.arange(20)[None, :].repeat(20, 0).astype(float)
    slope = features.slope_degrees(x, cell_x=30.0, cell_y=30.0)
    assert slope[10, 10] == pytest.approx(np.degrees(np.arctan(1 / 30)), abs=1e-6)


def test_distance_to_waterways_in_metres():
    # street along lat 3.0; waterway ~111 m north of it
    street = LineString([(101.0, 3.0), (101.01, 3.0)])
    water = LineString([(100.99, 3.001), (101.02, 3.001)])
    d = features.distance_to_waterways(gpd.GeoSeries([street], crs=4326), gpd.GeoSeries([water], crs=4326))
    assert d[0] == pytest.approx(110.6, abs=3)


def test_distance_without_waterways_is_nan():
    d = features.distance_to_waterways(gpd.GeoSeries([LineString([(101, 3), (101.01, 3)])], crs=4326),
                                       gpd.GeoSeries([], crs=4326))
    assert np.isnan(d[0])


def test_built_share_within_100m():
    n = 200
    cell = 0.0001  # ~11 m
    transform = from_origin(101.0, 3.02, cell, cell)
    landcover = np.full((n, n), 10, dtype="uint8")
    landcover[:, : n // 2] = 50                      # west half built-up
    west = LineString([(101.0 + 0.002, 3.01), (101.0 + 0.002, 3.012)])   # deep in the built half
    east = LineString([(101.0 + 0.018, 3.01), (101.0 + 0.018, 3.012)])   # deep in the other half
    share = features.built_up_share(gpd.GeoSeries([west, east], crs=4326), landcover, transform, 4326, buffer_m=100)
    assert share[0] == pytest.approx(1.0) and share[1] == pytest.approx(0.0)


def test_combine_ranks_equal_weight_and_direction():
    df = pd.DataFrame({"hand": [1, 5, 9], "twi": [9, 5, 1], "water_m": [10, 50, 90],
                       "slope": [0.1, 1, 2], "built": [0.9, 0.5, 0.1]})
    score = features.combine_ranks(df)           # street 0 is wettest on every criterion
    assert list(score.rank()) == [3.0, 2.0, 1.0]
    assert score[0] == pytest.approx(1.0) and score[2] == pytest.approx(0.0)


def test_combine_ranks_ignores_missing_feature_per_street():
    df = pd.DataFrame({"hand": [1, 9], "twi": [9, 1], "water_m": [np.nan, np.nan], "slope": [0.1, 2], "built": [0.9, 0.1]})
    score = features.combine_ranks(df)
    assert score[0] > score[1]


def test_fifths_are_even():
    classes = features.fifths(pd.Series(np.arange(50, dtype=float)))
    assert set(classes) == {1, 2, 3, 4, 5} and classes.value_counts().max() == 10
