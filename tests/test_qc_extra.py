"""wl_unresponsive review fixes: response lag, alert guard, duplicates, and loader wiring."""
import logging
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from floodready import live, qc, stations
from floodready.engine.replay import load_archive_readings
from test_qc_unresponsive import FIXTURES, STATIONS, level, rain, storm, wet, wl_flags


def test_lagged_onset_fixture_pekan_meru_is_not_blanked_when_the_river_answers_90_min_late():
    storm_df = pd.read_parquet(FIXTURES / "storm_20241112.parquet")
    st = pd.read_parquet(FIXTURES / "stations_storm.parquet")
    is_pm = (storm_df.graph_id == "PEKANMERU") & (storm_df.kind == "wl")
    pm = storm_df[is_pm].sort_values("time_local")
    lagged = pm.assign(time_local=pm.time_local + pd.Timedelta(minutes=90))
    pre_t = [lagged.time_local.min() - pd.Timedelta(minutes=15 * k) for k in range(1, 13)]
    pre = pd.DataFrame({"graph_id": "PEKANMERU", "kind": "wl", "time_local": pre_t, "rain_15min_mm": np.nan, "wl_m": pm.wl_m.iloc[0]})
    df = pd.concat([storm_df[~is_pm], pre, lagged], ignore_index=True)
    clean, flags = qc.clean_readings(df, stations=st)
    assert not (wl_flags(flags).graph_id == "PEKANMERU").any()
    out = clean[(clean.graph_id == "PEKANMERU") & (clean.kind == "wl")]
    assert out.wl_m.notna().all() and out.wl_m.max() > 4.2


def test_gauge_flat_at_or_above_alert_is_never_blanked():
    st = pd.concat([STATIONS[STATIONS.graph_id != "R"],
                    pd.DataFrame([{"graph_id": "R", "kind": "wl", "lat": 3.100, "lon": 101.400, "wl_alert_m": 3.5}])], ignore_index=True)
    lvl = np.concatenate([np.linspace(1.0, 4.5, 14), np.full(46, 4.5)])
    wetr = wet(np.full(60, 4.0))
    clean, flags = qc.clean_readings(pd.concat([wetr, level("R", lvl)], ignore_index=True), stations=st)
    assert wl_flags(flags).empty and clean[clean.kind == "wl"].wl_m.notna().all()
    _, flags = qc.clean_readings(pd.concat([wetr, level("R", lvl - 3.0)], ignore_index=True), stations=st)   # same shape, below alert
    assert not wl_flags(flags).empty


def test_duplicate_timestamps_do_not_crash():
    df = pd.concat([wet(storm()), level("R", np.full(40, 1.20))], ignore_index=True)
    df = pd.concat([df, df.iloc[[3, 45]]], ignore_index=True)
    qc.clean_readings(df, stations=STATIONS)


def test_loaders_pass_the_default_station_table(tmp_path, monkeypatch):
    sentinel = pd.DataFrame({"graph_id": ["X"], "kind": ["wl"], "lat": [1.0], "lon": [2.0]})
    seen = []
    real = qc.clean_readings
    monkeypatch.setattr(stations, "load_default", lambda: sentinel)
    monkeypatch.setattr(qc, "clean_readings", lambda r, stations=None: (seen.append(stations), real(r))[1])
    t = pd.date_range("2025-01-01", periods=4, freq="15min")
    (tmp_path / "rf").mkdir()
    pd.DataFrame({"graph_id": "G", "time_local": t, "rain_15min_mm": 0.0}).to_parquet(tmp_path / "rf" / "G.parquet")
    load_archive_readings(tmp_path, ["G"], datetime(2025, 1, 1), datetime(2025, 1, 2))
    assert seen and seen[-1] is sentinel
    live_dir = tmp_path / "live"
    (live_dir / "wl").mkdir(parents=True)
    pd.DataFrame({"graph_id": "R", "source_time": t, "wl_m": 1.0, "fetched_at_local": t}).to_parquet(live_dir / "wl" / "2025-01-01.parquet")
    n = len(seen)
    live.load_live_readings(live_dir, datetime(2025, 1, 1))
    assert len(seen) == n + 1 and seen[-1] is sentinel


def test_missing_station_table_warns_once(tmp_path, caplog, monkeypatch):
    monkeypatch.setattr(stations, "_warned", False)
    with caplog.at_level(logging.WARNING, logger="floodready.stations"):
        assert stations.load_default(tmp_path / "none.parquet") is None
        assert stations.load_default(tmp_path / "none.parquet") is None
    assert len([r for r in caplog.records if "wl_unresponsive" in r.getMessage()]) == 1
