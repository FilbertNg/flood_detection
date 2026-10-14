from floodready.gis import streets


def way(way_id, name, highway, coords):
    return {"type": "way", "id": way_id, "tags": {"name": name, "highway": highway} if name else {"highway": highway},
            "geometry": [{"lat": lat, "lon": lon} for lat, lon in coords]}


PAYLOAD = {"elements": [
    way(1, "Jalan Makyong 2K/KU5", "residential", [(3.0890, 101.4240), (3.0895, 101.4250)]),
    way(2, "Jalan Makyong 2K/KU5", "residential", [(3.0895, 101.4250), (3.0900, 101.4260)]),
    way(3, "Persiaran Sungai Keramat", "secondary", [(3.0830, 101.4060), (3.0832, 101.4070)]),
    way(4, None, "residential", [(3.0800, 101.4000), (3.0801, 101.4001)]),
    way(5, "Lorong Belakang", "service", [(3.0810, 101.4010), (3.0811, 101.4011)]),
    way(6, "Jalan Makyong 2K-KU5", "residential", [(3.0700, 101.4300), (3.0701, 101.4301)]),
]}


def test_slugify_street_names():
    assert streets.slugify("Jalan Makyong 2K/KU5") == "jalan-makyong-2k-ku5"
    assert streets.slugify("  Persiaran Sungai  Keramat ") == "persiaran-sungai-keramat"


def test_overpass_query_asks_for_named_roads_around_a_point():
    q = streets.overpass_query(3.0852, 101.4377, 3000)
    assert "around:3000,3.0852,101.4377" in q
    assert '["name"]' in q and "out geom" in q


def test_named_segments_are_merged_into_one_street():
    gdf = streets.streets_from_overpass(PAYLOAD, township_id="BBR")
    makyong = gdf[gdf.name == "Jalan Makyong 2K/KU5"]
    assert len(makyong) == 1
    assert makyong.iloc[0].street_id == "BBR-jalan-makyong-2k-ku5"
    assert 200 < makyong.iloc[0].length_m < 300  # two ~125 m segments


def test_unnamed_and_service_roads_are_dropped():
    gdf = streets.streets_from_overpass(PAYLOAD, township_id="BBR")
    assert "Lorong Belakang" not in set(gdf.name)
    assert gdf.name.notna().all()


def test_street_ids_are_unique_even_when_names_slugify_alike():
    gdf = streets.streets_from_overpass(PAYLOAD, township_id="BBR")
    assert gdf.street_id.is_unique
    assert {"BBR-jalan-makyong-2k-ku5", "BBR-jalan-makyong-2k-ku5-2"} <= set(gdf.street_id)


def test_output_is_wgs84_with_centroids():
    gdf = streets.streets_from_overpass(PAYLOAD, township_id="BBR")
    assert gdf.crs.to_epsg() == 4326
    row = gdf[gdf.name == "Persiaran Sungai Keramat"].iloc[0]
    assert abs(row.centroid_lat - 3.0831) < 0.001 and abs(row.centroid_lon - 101.4065) < 0.001
    assert row.township_id == "BBR" and row.highway == "secondary"


def test_tile_bboxes_cover_the_square_around_the_centre():
    tiles = streets.tile_bboxes(3.0852, 101.4377, radius_m=3000, n=4)
    assert len(tiles) == 16
    south = min(t[0] for t in tiles); west = min(t[1] for t in tiles)
    north = max(t[2] for t in tiles); east = max(t[3] for t in tiles)
    assert abs((north - south) * 111_320 - 6000) < 50          # 6 km tall
    assert abs((north + south) / 2 - 3.0852) < 1e-6 and abs((east + west) / 2 - 101.4377) < 1e-6


def test_bbox_query_uses_south_west_north_east_order():
    q = streets.overpass_bbox_query((3.05, 101.41, 3.06, 101.42))
    assert "way(3.05000,101.41000,3.06000,101.42000)" in q and "out geom" in q


def test_merge_payloads_drops_ways_seen_in_two_tiles():
    a = {"elements": PAYLOAD["elements"][:3]}
    b = {"elements": PAYLOAD["elements"][2:]}
    merged = streets.merge_payloads([a, b])
    assert [e["id"] for e in merged["elements"]] == [1, 2, 3, 4, 5, 6]
