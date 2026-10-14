from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
import yaml
from shapely.geometry import LineString

from floodready.api.runner import EngineContext, Runner

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "tests" / "fixtures" / "engine"
BBR = {"id": "BBR", "name": "Bandar Bukit Raja", "centre": {"lat": 3.0852, "lon": 101.4377},
       "stations": [{"graph_id": g, "types": t} for g, t in [("26558", ["RF", "WL"]), ("PEKANMERU", ["WL", "RF"]),
                    ("KGRANTAUPANJANG", ["RF"]), ("TELOKGONG", ["RF"]), ("PANDAMARAN", ["RF", "WL"]),
                    ("JLNBENTENGKAPAR", ["RF"]), ("SELATMUARA", ["RF", "WL"])]]}


def load_yaml(name):
    return yaml.safe_load((ROOT / "config" / name).read_text(encoding="utf-8"))


@pytest.fixture()
def context():
    readings = pd.read_csv(FIX / "bbr_20241112_readings.csv", parse_dates=["time_local"], dtype={"graph_id": str})
    stations = pd.read_csv(FIX / "stations.csv", dtype={"graph_id": str, "station_code": str})
    streets = gpd.GeoDataFrame(
        {"street_id": ["BBR-prone-street", "BBR-safe-street"], "name": ["Prone Street", "Safe Street"],
         "township_id": ["BBR", "BBR"], "susceptibility": [5, 1]},
        geometry=[LineString([(101.425, 3.089), (101.426, 3.090)]), LineString([(101.44, 3.095), (101.441, 3.096)])],
        crs=4326)
    return EngineContext(
        township=BBR, streets=streets, stations=stations,
        rules_cfg=load_yaml("rules.yaml"), matrix=load_yaml("risk_matrix.yaml")["matrix"], ml_cfg=load_yaml("ml.yaml"),
        tide=None,
        load_readings=lambda start, end: readings[(readings.time_local >= start) & (readings.time_local <= end)],
        load_live_readings=None,
        bundle_for=lambda when, live: None,
    )


@pytest.fixture()
def runner(context):
    return Runner(context)
