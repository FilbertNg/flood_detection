import json
import os
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import requests

from floodready import jobs, tide


class MarineStub:
    """Stands in for the Open-Meteo marine API: a smooth tide over the requested days (test stub, not data)."""

    def __init__(self):
        self.requests = []

    def get(self, url, params=None, timeout=None):
        self.requests.append((url, dict(params or {})))
        idx = pd.date_range(params["start_date"], pd.Timestamp(params["end_date"]) + pd.Timedelta(hours=23), freq="h")
        h = np.asarray((idx - pd.Timestamp("2024-01-01")) / pd.Timedelta(hours=1))
        vals = (1.5 * np.sin(2 * np.pi * h / 12.42) + 0.4 * np.sin(2 * np.pi * h / 12.0)).round(3).tolist()
        body = json.dumps({"hourly": {"time": [t.strftime("%Y-%m-%dT%H:%M") for t in idx], "sea_level_height_msl": vals}})
        r = requests.Response()
        r.status_code = 200
        r._content = body.encode()
        r.encoding = "utf-8"
        return r


def _bump_mtime(path, seconds=5):
    st = path.stat()
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + seconds * 1_000_000_000))


def test_refresh_downloads_current_year_to_today_plus_3_days_and_rebuilds_the_table(tmp_path):
    raw, out = tmp_path / "raw", tmp_path / "interim" / "tide_hourly.parquet"
    session = MarineStub()
    summary = jobs.run_tide_refresh(session, raw, out, date(2026, 10, 16))
    assert len(session.requests) == 1
    p = session.requests[0][1]
    assert p["start_date"] == "2026-01-01" and p["end_date"] == "2026-10-19"
    table = pd.read_parquet(out)
    assert table.time_local.max() == pd.Timestamp("2026-10-19 23:00")
    assert {"tide_height_m", "hours_to_high_tide", "tide_filled"} <= set(table)
    assert summary["last_hour"] == "2026-10-19 23:00:00"


def test_refresh_due_once_per_day_and_not_hammered_after_a_failure(tmp_path):
    out = tmp_path / "tide_hourly.parquet"
    now = datetime(2026, 10, 16, 9, 0)
    assert jobs.tide_refresh_due(out, now)                                    # no table yet
    pd.DataFrame({"x": [1]}).to_parquet(out)
    os.utime(out, (now.timestamp(), now.timestamp()))
    assert not jobs.tide_refresh_due(out, now + timedelta(hours=3))           # refreshed today
    tomorrow = now + timedelta(days=1)
    assert jobs.tide_refresh_due(out, tomorrow)                               # a new day
    assert not jobs.tide_refresh_due(out, tomorrow, last_attempt=tomorrow - timedelta(hours=1))
    assert jobs.tide_refresh_due(out, tomorrow, last_attempt=tomorrow - timedelta(hours=7))


def test_tide_table_reloads_when_the_parquet_changes(tmp_path):
    path = tmp_path / "tide_hourly.parquet"
    cache = tide.TideTable(path)
    assert cache.get() is None
    pd.DataFrame({"time_local": [pd.Timestamp("2026-10-16")], "tide_height_m": [1.0]}).to_parquet(path)
    assert len(cache.get()) == 1
    assert cache.get() is cache.get()                                         # unchanged file: no re-read
    pd.DataFrame({"time_local": pd.date_range("2026-10-16", periods=3, freq="h"), "tide_height_m": 1.0}).to_parquet(path)
    _bump_mtime(path)
    assert len(cache.get()) == 3


def test_tide_table_keeps_the_old_table_if_the_new_file_is_unreadable(tmp_path):
    path = tmp_path / "tide_hourly.parquet"
    pd.DataFrame({"time_local": [pd.Timestamp("2026-10-16")], "tide_height_m": [1.0]}).to_parquet(path)
    cache = tide.TideTable(path)
    assert len(cache.get()) == 1
    path.write_bytes(b"not parquet")
    _bump_mtime(path)
    assert len(cache.get()) == 1
