import json
import logging

from floodready.engine import street_stations as ss

GAUGES = [("A", 3.100, 101.400), ("B", 3.110, 101.400), ("C", 3.300, 101.400), ("D", 3.400, 101.400)]


def test_rain_gauges_within_the_radius_else_the_nearest_minimum():
    assert ss.rain_gauges(3.103, 101.400, GAUGES) == ["A", "B"]          # both within 1 km
    assert ss.rain_gauges(3.350, 101.400, GAUGES, {"rain_radius_km": 5}) == ["C", "D"]   # none within 5 km: nearest two


def test_radius_and_minimum_gauges_are_parameters():
    cfg = {"rain_radius_km": 12, "min_rain_gauges": 2, "river_radius_km": 10}
    assert ss.rain_gauges(3.103, 101.400, GAUGES, cfg) == ["A", "B"]          # C is ~22 km away
    assert ss.rain_gauges(3.103, 101.400, GAUGES, {**cfg, "rain_radius_km": 1, "min_rain_gauges": 3}) == ["A", "B", "C"]


def test_nearest_river_station_within_the_configured_radius():
    wl = [("W1", 3.10, 101.40)]
    assert ss.pick_wl([], wl, 3.17, 101.40, {"river_radius_km": 10})[:2] == ("W1", "nearest")     # ~7.8 km
    assert ss.pick_wl([], wl, 3.17, 101.40, {"river_radius_km": 5}) == (None, None, None)


def test_wl_station_first_on_the_flow_path_within_15_km():
    wl = [("W1", 3.10, 101.40), ("W2", 3.11, 101.40)]
    hits = [("W2", 9_000.0), ("W1", 12_000.0)]
    assert ss.pick_wl(hits, wl, 3.2, 101.4) == ("W2", "flow", 9_000.0)


def test_flow_hit_beyond_15_km_is_ignored_and_nearest_within_the_river_radius_used():
    wl = [("W1", 3.10, 101.40), ("W2", 3.30, 101.40)]
    wl_id, method, dist = ss.pick_wl([("W2", 16_000.0)], wl, 3.102, 101.40)
    assert (wl_id, method) == ("W1", "nearest") and 200 < dist < 250


def test_no_flow_and_no_river_within_the_radius_gives_null():
    assert ss.pick_wl([], [("W1", 3.30, 101.40)], 3.10, 101.40, {"river_radius_km": 5}) == (None, None, None)


def test_load_returns_none_and_warns_when_the_file_is_missing(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        assert ss.load(tmp_path / "nope.json") is None
    assert "township" in caplog.text.lower()


def test_stations_for_drops_duplicates(tmp_path):
    path = tmp_path / "m.json"
    path.write_text(json.dumps({"S": {"wl": "26558", "rf": ["26558", "R2"], "method": "flow", "distance_m": 1.0}}))
    assert ss.stations_for(ss.load(path), "S") == ("26558", "R2")


def test_stations_for_puts_the_river_station_first(tmp_path):
    path = tmp_path / "m.json"
    path.write_text(json.dumps({"S1": {"wl": "W1", "rf": ["R1", "R2"], "method": "flow", "distance_m": 10.0},
                                "S2": {"wl": None, "rf": ["R2"], "method": None, "distance_m": None}}))
    mapping = ss.load(path)
    assert ss.stations_for(mapping, "S1") == ("W1", "R1", "R2")
    assert ss.stations_for(mapping, "S2") == ("R2",)
    assert ss.stations_for(mapping, "unknown") is None
    assert ss.wl_for(mapping, "S1") == "W1" and ss.wl_for(mapping, "S2") is None
