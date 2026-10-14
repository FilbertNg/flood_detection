import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest
import requests

from floodready import met, openmeteo, storage
from floodready.http import fetch_text

FIX = Path(__file__).parent / "fixtures"


# ---------- HTTP with retries ----------

class FlakySession:
    """Fails a set number of times, then answers."""

    def __init__(self, failures):
        self.failures = failures
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        if self.calls <= self.failures:
            raise requests.ConnectionError("down")
        response = requests.Response()
        response.status_code = 200
        response._content = b"ok"
        response.encoding = "utf-8"
        return response


def test_fetch_text_retries_then_succeeds():
    session = FlakySession(failures=2)
    assert fetch_text(session, "https://x", retries=3, backoff_s=0) == "ok"
    assert session.calls == 3


def test_fetch_text_gives_up_after_retries():
    session = FlakySession(failures=5)
    with pytest.raises(requests.ConnectionError):
        fetch_text(session, "https://x", retries=3, backoff_s=0)
    assert session.calls == 3


# ---------- storage ----------

def test_append_parquet_creates_then_appends_without_duplicates(tmp_path):
    path = tmp_path / "day.parquet"
    first = pd.DataFrame({"graph_id": ["A", "B"], "source_time": [1, 1], "wl_m": [1.0, 2.0]})
    second = pd.DataFrame({"graph_id": ["B", "C"], "source_time": [1, 1], "wl_m": [2.0, 3.0]})
    storage.append_parquet(first, path, keys=["graph_id", "source_time"])
    storage.append_parquet(second, path, keys=["graph_id", "source_time"])
    result = pd.read_parquet(path)
    assert sorted(result["graph_id"]) == ["A", "B", "C"]


def test_save_raw_gzip_round_trips(tmp_path):
    path = storage.save_raw(tmp_path / "x" / "page.html.gz", "<html>é</html>")
    assert storage.read_raw(path) == "<html>é</html>"


# ---------- MET warnings ----------

def test_flatten_warnings_extracts_issue_and_validity():
    rows = met.flatten_warnings(json.loads((FIX / "met_warning.json").read_text(encoding="utf-8")))
    assert len(rows) == 3
    first = rows[0]
    assert first["issued"] == datetime(2026, 10, 14, 16, 30)
    assert first["title_en"] == "Strong Winds and Rough Seas Warning"
    assert first["valid_from"] == datetime(2026, 10, 14, 0, 0)
    assert "text_en" in first and "text_bm" in first


# ---------- Open-Meteo forecast ----------

def test_flatten_forecast_makes_long_rows_per_point_model_hour():
    payload = json.loads((FIX / "openmeteo_forecast_2pts_2models.json").read_text(encoding="utf-8"))
    rows = openmeteo.flatten_forecast(payload, point_ids=["BBR", "USJ"], models=["best_match", "gfs_seamless"])
    assert len(rows) == 2 * 2 * 6
    row = next(r for r in rows if r["point_id"] == "BBR" and r["model"] == "best_match")
    assert row["time_local"] == datetime(2026, 10, 14, 20, 0)
    assert row["precip_prob_pct"] == 51
    assert {r["point_id"] for r in rows} == {"BBR", "USJ"}
