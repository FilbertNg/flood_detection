"""QC is applied at both loaders, so every consumer (rules, ML, API) sees clean data."""
from datetime import datetime
from pathlib import Path

import pandas as pd

from floodready import live
from floodready.engine.replay import load_archive_readings

T = lambda hhmm, day=14: datetime(2026, 10, day, int(hhmm[:2]), int(hhmm[3:]))  # noqa: E731


def test_load_live_readings_applies_qc(tmp_path):
    (tmp_path / "rf").mkdir()
    (tmp_path / "wl").mkdir()
    times = [T("08:00"), T("08:15"), T("08:30"), T("08:45")]
    pd.DataFrame({"graph_id": "G", "source_time": times, "fetched_at_local": times,
                  "rain_since_midnight_mm": [1.0, 2.0, 402.0, 403.0]}).to_parquet(tmp_path / "rf" / "2026-10-14.parquet")
    pd.DataFrame({"graph_id": "R", "source_time": times, "fetched_at_local": times,
                  "wl_m": [3.0, 3.1, 6.0, 3.1]}).to_parquet(tmp_path / "wl" / "2026-10-14.parquet")
    out = live.load_live_readings(tmp_path, T("08:00"))
    rf = out[out.kind == "rf"].set_index("time_local").rain_15min_mm
    assert rf.loc[T("08:15")] == 1.0 and pd.isna(rf.loc[T("08:30")]) and rf.loc[T("08:45")] == 1.0
    wl = out[out.kind == "wl"].set_index("time_local").wl_m
    assert pd.isna(wl.loc[T("08:30")]) and wl.loc[T("08:15")] == 3.1


def test_load_archive_readings_applies_qc_on_the_full_history(tmp_path):
    for kind in ("rf", "wl"):
        (tmp_path / kind).mkdir()
    t = pd.date_range("2025-01-01", periods=6, freq="15min")
    pd.DataFrame({"graph_id": "G", "time_local": t, "rain_15min_mm": [0, -2500.0, 3, 0, 150.0, 2]}) \
        .to_parquet(tmp_path / "rf" / "G.parquet")
    pd.DataFrame({"graph_id": "R", "time_local": t, "wl_m": [3.0, 3.1, 5.5, 3.1, 3.2, 3.2]}) \
        .to_parquet(tmp_path / "wl" / "R.parquet")
    out = load_archive_readings(Path(tmp_path), ["G", "R"], datetime(2025, 1, 1, 0, 15), datetime(2025, 1, 1, 1, 15))
    rf = out[out.kind == "rf"].set_index("time_local").rain_15min_mm
    assert len(rf) == 5 and pd.isna(rf.loc["2025-01-01 00:15"]) and pd.isna(rf.loc["2025-01-01 01:00"])
    assert rf.loc["2025-01-01 00:30"] == 3 and rf.loc["2025-01-01 01:15"] == 2
    wl = out[out.kind == "wl"].set_index("time_local").wl_m
    assert pd.isna(wl.loc["2025-01-01 00:30"]) and wl.loc["2025-01-01 00:15"] == 3.1
