import logging
from datetime import datetime

import numpy as np
import pandas as pd

from floodready import live

T = lambda hhmm, day=14: datetime(2026, 10, day, int(hhmm[:2]), int(hhmm[3:]))  # noqa: E731


def test_rain_per_quarter_is_the_difference_of_rain_since_midnight():
    rf = pd.DataFrame({
        "graph_id": ["26558"] * 4, "source_time": [T("08:00"), T("08:15"), T("08:30"), T("08:30")],
        "rain_since_midnight_mm": [10.0, 14.0, 20.5, 20.5],            # last row: same reading logged twice
    })
    out = live.rain_readings(rf).set_index("time_local")
    assert out.loc[T("08:15"), "rain_15min_mm"] == 4.0
    assert out.loc[T("08:30"), "rain_15min_mm"] == 6.5
    assert len(out) == 2                                              # first reading has no previous value


def test_midnight_reset_counts_the_new_days_total():
    rf = pd.DataFrame({"graph_id": ["X"] * 2, "source_time": [T("23:45", 14), T("00:00", 15)],
                       "rain_since_midnight_mm": [30.0, 1.5]})
    out = live.rain_readings(rf)
    assert out.rain_15min_mm.tolist() == [1.5]


def test_water_level_readings_keep_the_source_time():
    wl = pd.DataFrame({"graph_id": ["PEKANMERU"] * 2, "source_time": [T("19:30"), T("19:45")], "wl_m": [3.2, None]})
    out = live.level_readings(wl)
    assert out.kind.unique().tolist() == ["wl"] and out.wl_m.tolist()[0] == 3.2
    assert set(out.columns) == {"graph_id", "kind", "time_local", "rain_15min_mm", "wl_m"}


def test_a_corrected_live_reading_replaces_the_placeholder():
    wl = pd.DataFrame({"graph_id": ["PEKANMERU"] * 2, "source_time": [T("01:00")] * 2, "wl_m": [0.0, 3.15],
                       "fetched_at_local": [T("01:02"), T("01:16")]})
    assert live.level_readings(wl).wl_m.tolist() == [3.15]


# ---- QC over archive tail + live (train/serve parity) ----

def _write_live_rf(live_dir, rows):
    d = live_dir / "rf"
    d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=["graph_id", "source_time", "rain_since_midnight_mm"]).to_parquet(d / "2026-10-14.parquet")


def _write_archive_rf(hist_dir, gid, times, values):
    d = hist_dir / "rf"
    d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"graph_id": gid, "time_local": times, "rain_15min_mm": values}).to_parquet(d / f"{gid}.parquet")


def _stuck_setup(tmp_path):
    """The same 25.0 mm reading three times within 24 h, but only the last one inside the 6 h live window."""
    live_dir, hist = tmp_path / "jps_live", tmp_path / "jps_hist"
    _write_live_rf(live_dir, [("G", T("11:45"), 5.0), ("G", T("12:00"), 30.0), ("G", T("12:15"), 30.0)])
    times = pd.date_range("2026-10-13 12:00", "2026-10-14 11:30", freq="15min")
    vals = np.zeros(len(times))
    for stamp in ("2026-10-13 16:00", "2026-10-14 02:00"):
        vals[list(times).index(pd.Timestamp(stamp))] = 25.0
    _write_archive_rf(hist, "G", times, vals)
    return live_dir, hist


def test_gauge_stuck_beyond_the_live_window_is_flagged_with_the_archive_tail(tmp_path):
    live_dir, hist = _stuck_setup(tmp_path)
    since = T("06:00")
    live_only = live.load_live_readings(live_dir, since, {"G"}, stations=None, archive_dir=tmp_path / "nope")
    assert live_only.rain_15min_mm.max() == 25.0                       # alone, the live window cannot see it is stuck
    out = live.load_live_readings(live_dir, since, {"G"}, stations=None, archive_dir=hist)
    assert out.time_local.min() >= pd.Timestamp(since)                 # only the requested window comes back
    assert out[out.time_local == T("12:00")].rain_15min_mm.isna().all()


def test_live_row_wins_over_the_archive_row_for_the_same_time(tmp_path):
    live_dir, hist = tmp_path / "jps_live", tmp_path / "jps_hist"
    _write_live_rf(live_dir, [("G", T("11:45"), 5.0), ("G", T("12:00"), 8.0)])       # 3.0 mm live
    times = pd.date_range("2026-10-14 11:00", "2026-10-14 12:00", freq="15min")
    _write_archive_rf(hist, "G", times, np.full(len(times), 1.0))
    out = live.load_live_readings(live_dir, T("11:00"), {"G"}, stations=None, archive_dir=hist)
    assert out[out.time_local == T("12:00")].rain_15min_mm.tolist() == [3.0]


def test_nothing_after_until_is_used(tmp_path):
    live_dir, hist = _stuck_setup(tmp_path)
    out = live.load_live_readings(live_dir, T("06:00"), {"G"}, stations=None, archive_dir=hist, until=T("12:00"))
    assert out.time_local.max() <= T("12:00")
    assert out[out.time_local == T("12:00")].rain_15min_mm.isna().all()


def test_missing_archive_degrades_to_live_only_with_one_warning(tmp_path, caplog):
    live_dir, _ = _stuck_setup(tmp_path)
    with caplog.at_level(logging.WARNING, logger="floodready.live"):
        out = live.load_live_readings(live_dir, T("06:00"), {"G"}, stations=None, archive_dir=tmp_path / "nope")
    assert out.rain_15min_mm.max() == 25.0
    assert len([r for r in caplog.records if r.name == "floodready.live"]) == 1


def test_archive_tail_is_cached_per_file_mtime(tmp_path, monkeypatch):
    live_dir, hist = _stuck_setup(tmp_path)
    calls = []
    real = pd.read_parquet

    def spy(p, *a, **k):
        calls.append(str(p))
        return real(p, *a, **k)

    monkeypatch.setattr(live.pd, "read_parquet", spy)
    live.load_live_readings(live_dir, T("06:00"), {"G"}, stations=None, archive_dir=hist)
    live.load_live_readings(live_dir, T("06:00"), {"G"}, stations=None, archive_dir=hist)
    assert len([c for c in calls if "jps_hist" in c]) == 1
