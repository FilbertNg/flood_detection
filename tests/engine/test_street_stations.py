import json
import logging

from floodready.engine import street_stations as ss

GAUGES = [("A", 3.100, 101.400), ("B", 3.110, 101.400), ("C", 3.300, 101.400), ("D", 3.400, 101.400)]


def test_rain_gauges_within_5_km_else_nearest_two():
    assert ss.rain_gauges(3.103, 101.400, GAUGES) == ["A", "B"]          # both within 1 km
    assert ss.rain_gauges(3.350, 101.400, GAUGES) == ["C", "D"]          # none within 5 km: nearest two


def test_wl_station_first_on_the_flow_path_within_15_km():
    wl = [("W1", 3.10, 101.40), ("W2", 3.11, 101.40)]
    hits = [("W2", 9_000.0), ("W1", 12_000.0)]
    assert ss.pick_wl(hits, wl, 3.2, 101.4) == ("W2", "flow", 9_000.0)


def test_flow_hit_beyond_15_km_is_ignored_and_nearest_within_5_km_used():
    wl = [("W1", 3.10, 101.40), ("W2", 3.30, 101.40)]
    wl_id, method, dist = ss.pick_wl([("W2", 16_000.0)], wl, 3.102, 101.40)
    assert (wl_id, method) == ("W1", "nearest") and 200 < dist < 250


def test_no_flow_and_no_river_within_5_km_gives_null():
    assert ss.pick_wl([], [("W1", 3.30, 101.40)], 3.10, 101.40) == (None, None, None)


def test_load_returns_none_and_warns_when_the_file_is_missing(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        assert ss.load(tmp_path / "nope.json") is None
    assert "township" in caplog.text.lower()


def test_stations_for_puts_the_river_station_first(tmp_path):
    path = tmp_path / "m.json"
    path.write_text(json.dumps({"S1": {"wl": "W1", "rf": ["R1", "R2"], "method": "flow", "distance_m": 10.0},
                                "S2": {"wl": None, "rf": ["R2"], "method": None, "distance_m": None}}))
    mapping = ss.load(path)
    assert ss.stations_for(mapping, "S1") == ("W1", "R1", "R2")
    assert ss.stations_for(mapping, "S2") == ("R2",)
    assert ss.stations_for(mapping, "unknown") is None
    assert ss.wl_for(mapping, "S1") == "W1" and ss.wl_for(mapping, "S2") is None
