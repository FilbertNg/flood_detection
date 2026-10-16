import gzip
import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
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

ROOT = Path(__file__).resolve().parents[1]


def _marine_json(times, values):
    return json.dumps({"hourly": {"time": [t.strftime("%Y-%m-%dT%H:%M") for t in times], "sea_level_height_msl": values}})


def _two_year_table(tmp_path):
    """An existing table covering 2024-01-01 .. 2026-10-19 built through the real pipeline from a stub."""
    raw = tmp_path / "seed_raw"
    stub = MarineStub()
    for start, end in (("2024-01-01", "2025-12-31"), ("2026-01-01", "2026-10-19")):
        text = stub.get("u", {"start_date": start, "end_date": end}).text
        tide_save = raw / f"{start.replace('-', '')}_{end.replace('-', '')}.json.gz"
        tide_save.parent.mkdir(parents=True, exist_ok=True)
        tide_save.write_bytes(gzip.compress(text.encode()))
    out = tmp_path / "interim" / "tide_hourly.parquet"
    tide.build_hourly_table(raw, out)
    return out


def test_refresh_without_the_raw_history_never_shrinks_the_table(tmp_path):
    out = _two_year_table(tmp_path)
    old = pd.read_parquet(out)
    jobs.run_tide_refresh(MarineStub(), tmp_path / "empty_raw", out, date(2026, 10, 16))
    new = pd.read_parquet(out)
    assert new.time_local.min() == old.time_local.min() == pd.Timestamp("2024-01-01")
    assert len(new) >= len(old)
    assert pd.Timestamp("2024-11-12 08:00") in set(new.time_local)


def test_a_rebuild_that_would_shrink_the_table_is_refused_and_the_old_file_kept(tmp_path):
    out = _two_year_table(tmp_path)
    before = out.read_bytes()
    raw = tmp_path / "short_raw"
    raw.mkdir()
    short = MarineStub().get("u", {"start_date": "2026-01-01", "end_date": "2026-10-19"}).text
    (raw / "20260101_20261019.json.gz").write_bytes(gzip.compress(short.encode()))
    with pytest.raises(RuntimeError):
        tide.build_hourly_table(raw, out, seed_from_existing=False)
    assert out.read_bytes() == before


def test_an_error_payload_is_not_cached_and_does_not_poison_later_runs(tmp_path):
    raw, out = tmp_path / "raw", tmp_path / "t.parquet"

    class Bad(MarineStub):
        def get(self, url, params=None, timeout=None):
            r = requests.Response()
            r.status_code = 200
            r._content = json.dumps({"error": True, "reason": "limit"}).encode()
            r.encoding = "utf-8"
            return r

    with pytest.raises(ValueError):
        jobs.run_tide_refresh(Bad(), raw, out, date(2026, 10, 16))
    assert not list(raw.glob("*"))
    jobs.run_tide_refresh(MarineStub(), raw, out, date(2026, 10, 16))
    assert out.exists()


def test_an_unparseable_cached_chunk_is_skipped_with_a_warning(tmp_path, caplog):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "20240101_20240102.json.gz").write_bytes(gzip.compress(b'{"error": true}'))
    good = MarineStub().get("u", {"start_date": "2026-01-01", "end_date": "2026-01-10"}).text
    (raw / "20260101_20260110.json.gz").write_bytes(gzip.compress(good.encode()))
    series = tide.load_cached(raw)
    assert series.index.min() == pd.Timestamp("2026-01-01") and "20240101_20240102" in caplog.text


def test_save_raw_is_atomic_no_tmp_left(tmp_path):
    from floodready import storage
    storage.save_raw(tmp_path / "a" / "x.json.gz", "{}")
    assert [p.name for p in (tmp_path / "a").iterdir()] == ["x.json.gz"]


def test_refresh_due_uses_myt_even_when_the_process_timezone_is_utc(tmp_path):
    out = tmp_path / "t.parquet"
    out.write_bytes(b"x")
    written_myt = datetime(2026, 10, 17, 0, 30)                             # 16:30 UTC on the 16th
    ts = (written_myt - timedelta(hours=8)).replace(tzinfo=__import__("datetime").timezone.utc).timestamp()
    os.utime(out, (ts, ts))
    code = ("from datetime import datetime; from pathlib import Path; from floodready import jobs; "
            f"print(jobs.tide_refresh_due(Path(r'{out}'), datetime(2026, 10, 17, 6, 0)))")
    res = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env={**os.environ, "TZ": "UTC0"}, capture_output=True, text=True)
    assert res.stdout.strip() == "False", res.stderr


def test_a_failed_attempt_is_remembered_across_runs(tmp_path):
    out = tmp_path / "t.parquet"
    now = datetime(2026, 10, 16, 9, 0)
    assert jobs.tide_refresh_due(out, now, jobs.read_tide_attempt(out))
    jobs.write_tide_attempt(out, now)
    assert not jobs.tide_refresh_due(out, now + timedelta(minutes=15), jobs.read_tide_attempt(out))
    assert jobs.tide_refresh_due(out, now + timedelta(hours=7), jobs.read_tide_attempt(out))


def test_null_values_in_a_newer_chunk_do_not_override_real_values_in_an_older_one(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    idx = pd.date_range("2026-10-01", periods=48, freq="h")
    (raw / "20260101_20261002.json.gz").write_bytes(gzip.compress(_marine_json(idx, [1.0] * 48).encode()))
    newer = [None] * 24 + [2.0] * 24
    (raw / "20260101_20261003.json.gz").write_bytes(gzip.compress(_marine_json(idx, newer).encode()))
    s = tide.load_cached(raw)
    assert s.iloc[:24].eq(1.0).all() and s.iloc[24:].eq(2.0).all()


def test_superseded_chunks_with_the_same_start_are_deleted_after_a_refresh(tmp_path):
    raw, out = tmp_path / "raw", tmp_path / "t.parquet"
    jobs.run_tide_refresh(MarineStub(), raw, out, date(2026, 10, 16))
    jobs.run_tide_refresh(MarineStub(), raw, out, date(2026, 10, 17))
    assert [p.name for p in raw.glob("*.json.gz")] == ["20260101_20261020.json.gz"]


def test_a_locked_table_file_is_retried_then_the_old_one_is_kept(tmp_path, monkeypatch):
    out = _two_year_table(tmp_path)
    before = out.read_bytes()
    calls = []
    real = Path.replace

    def locked(self, target):
        calls.append(1)
        raise PermissionError(5, "locked")

    monkeypatch.setattr(Path, "replace", locked)
    monkeypatch.setattr(tide.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError):
        tide.build_hourly_table(tmp_path / "seed_raw", out)
    assert len(calls) >= 3 and out.read_bytes() == before
    assert not list(out.parent.glob("*.tmp"))

def test_a_superseded_chunk_is_kept_if_it_has_real_hours_the_new_one_lacks(tmp_path):
    raw, out = tmp_path / "raw", tmp_path / "t.parquet"
    raw.mkdir()

    class Nulls(MarineStub):
        def get(self, url, params=None, timeout=None):
            r = super().get(url, params, timeout)
            body = json.loads(r.text)
            body["hourly"]["sea_level_height_msl"][100:110] = [None] * 10
            r._content = json.dumps(body).encode()
            return r

    jobs.run_tide_refresh(MarineStub(), raw, out, date(2026, 10, 16))
    jobs.run_tide_refresh(Nulls(), raw, out, date(2026, 10, 17))
    assert len(list(raw.glob("*.json.gz"))) == 2
    real = tide.load_cached(raw)
    assert real.index.min() == pd.Timestamp("2026-01-01") and real.iloc[100:110].notna().all()


def test_seeded_and_fresh_rebuilds_write_the_same_timestamp_unit(tmp_path):
    out = _two_year_table(tmp_path)
    fresh = pd.read_parquet(out)
    jobs.run_tide_refresh(MarineStub(), tmp_path / "empty_raw", out, date(2026, 10, 16))
    seeded = pd.read_parquet(out)
    assert str(fresh.time_local.dtype) == str(seeded.time_local.dtype) == "datetime64[us]"


def test_a_failing_attempt_marker_write_is_logged_not_fatal(tmp_path, monkeypatch, caplog):
    import importlib.util
    spec = importlib.util.spec_from_file_location("run_loggers_mod", ROOT / "scripts" / "run_loggers.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "TIDE_OUT", tmp_path / "t.parquet")
    monkeypatch.setattr(mod.jobs, "write_tide_attempt", lambda *a: (_ for _ in ()).throw(OSError("disk full")))
    monkeypatch.setattr(mod.jobs, "run_tide_refresh", lambda *a: {})
    mod.maybe_refresh_tide(None)
    assert "tide_refresh failed" in caplog.text
