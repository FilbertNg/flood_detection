import pandas as pd

from floodready.ml import dataset

STATIONS = pd.DataFrame([
    {"graph_id": "RIVER", "kind": "wl", "lat": 3.10, "lon": 101.40},
    {"graph_id": "UPSTREAM", "kind": "wl", "lat": 3.15, "lon": 101.55},   # ~17 km away, linked by the network
    {"graph_id": "GAUGE", "kind": "rf", "lat": 3.11, "lon": 101.41},
    {"graph_id": "FAR", "kind": "rf", "lat": 3.60, "lon": 101.90},        # > 25 km
])
TOWN = {"stations": [{"graph_id": "RIVER", "types": ["WL"]}, {"graph_id": "LOCALRF", "types": ["RF"]}]}


def test_serving_loads_the_upstream_stations_the_model_was_trained_with():
    archived = {"RIVER", "UPSTREAM", "GAUGE", "FAR", "LOCALRF"}
    ids = dataset.township_station_ids(TOWN, STATIONS, archived, network={"RIVER": ["UPSTREAM"]})
    assert ids == ["GAUGE", "LOCALRF", "RIVER", "UPSTREAM"]


def test_only_archived_stations_are_requested():
    ids = dataset.township_station_ids(TOWN, STATIONS, {"RIVER", "GAUGE"}, network={"RIVER": ["UPSTREAM"]})
    assert ids == ["GAUGE", "RIVER"]
