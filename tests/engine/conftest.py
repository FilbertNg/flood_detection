from pathlib import Path

import pandas as pd
import pytest
import yaml

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "engine"
ROOT = Path(__file__).resolve().parents[2]
BBR_STATIONS = ["26558", "PEKANMERU", "KGRANTAUPANJANG", "TELOKGONG", "PANDAMARAN", "JLNBENTENGKAPAR", "SELATMUARA"]


@pytest.fixture(scope="session")
def readings():
    """Real JPS readings for all BBR stations, 11-12 Nov 2024."""
    df = pd.read_csv(FIX / "bbr_20241112_readings.csv", parse_dates=["time_local"], dtype={"graph_id": str})
    return df


@pytest.fixture(scope="session")
def stations():
    return pd.read_csv(FIX / "stations.csv", dtype={"graph_id": str, "station_code": str})


@pytest.fixture(scope="session")
def rules_cfg():
    return yaml.safe_load((ROOT / "config" / "rules.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def matrix_cfg():
    return yaml.safe_load((ROOT / "config" / "risk_matrix.yaml").read_text(encoding="utf-8"))["matrix"]
