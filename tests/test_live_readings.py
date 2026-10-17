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


def test_archive_row_wins_over_the_live_row_for_the_same_time(tmp_path):
    live_dir, hist = tmp_path / "jps_live", tmp_path / "jps_hist"
    _write_live_rf(live_dir, [("G", T("11:45"), 5.0), ("G", T("12:00"), 8.0)])       # 3.0 mm live
    times = pd.date_range("2026-10-14 11:00", "2026-10-14 12:00", freq="15min")
    _write_archive_rf(hist, "G", times, np.full(len(times), 1.0))
    out = live.load_live_readings(live_dir, T("11:00"), {"G"}, stations=None, archive_dir=hist)
    assert out[out.time_local == T("12:00")].rain_15min_mm.tolist() == [1.0]       # JPS's later archive record


def test_nothing_after_until_is_used(tmp_path):
    live_dir, hist = _stuck_setup(tmp_path)
    out = live.load_live_readings(live_dir, T("06:00"), {"G"}, stations=None, archive_dir=hist, until=T("12:00"))
    assert out.time_local.max() <= T("12:00")
    assert out[out.time_local == T("12:00")].rain_15min_mm.isna().all()


def test_missing_archive_degrades_to_live_only_with_one_warning(tmp_path, caplog, monkeypatch):
    monkeypatch.setattr(live, "_warned_no_archive", False)
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


# ---- review fixes ----

def test_flat_run_longer_than_two_days_is_flagged_live(tmp_path):
    """wl_unresponsive has no fixed look-back: the heavy rain that started the run fell 4 days before the live window."""
    live_dir, hist = tmp_path / "jps_live", tmp_path / "jps_hist"
    stations = pd.DataFrame([{"graph_id": "R", "kind": "wl", "lat": 3.1, "lon": 101.4, "wl_alert_m": 10.0},
                             {"graph_id": "G", "kind": "rf", "lat": 3.12, "lon": 101.4},
                             {"graph_id": "G2", "kind": "rf", "lat": 3.11, "lon": 101.42}])      # the rule needs two wet gauges
    times = pd.date_range("2026-10-10 00:00", "2026-10-14 22:45", freq="15min")
    rain = np.zeros(len(times))
    rain[16:28] = 10.0                                                  # 3 h of heavy rain on 10 Oct 04:00-07:00
    _write_archive_rf(hist, "G", times, rain)
    _write_archive_rf(hist, "G2", times, rain)
    (hist / "wl").mkdir(parents=True)
    pd.DataFrame({"graph_id": "R", "time_local": times, "wl_m": 3.0}).to_parquet(hist / "wl" / "R.parquet")
    (live_dir / "wl").mkdir(parents=True)
    live_times = pd.date_range("2026-10-14 23:00", "2026-10-14 23:45", freq="15min")
    pd.DataFrame({"graph_id": "R", "source_time": live_times, "wl_m": 3.0}).to_parquet(live_dir / "wl" / "2026-10-14.parquet")
    out = live.load_live_readings(live_dir, T("00:00"), {"R", "G", "G2"}, stations=stations, archive_dir=hist)
    assert len(out) == 4 and out.wl_m.isna().all()


def test_a_reading_after_until_cannot_change_a_flag(tmp_path):
    live_dir, hist = tmp_path / "jps_live", tmp_path / "jps_hist"
    _write_live_rf(live_dir, [("G", T("11:45"), 5.0), ("G", T("12:00"), 30.0), ("G", T("12:15"), 55.0)])  # 25.0 then 25.0
    times = pd.date_range("2026-10-14 01:00", "2026-10-14 11:30", freq="15min")
    vals = np.zeros(len(times))
    vals[list(times).index(pd.Timestamp("2026-10-14 02:00"))] = 25.0
    _write_archive_rf(hist, "G", times, vals)
    later = live.load_live_readings(live_dir, T("06:00"), {"G"}, stations=None, archive_dir=hist)
    assert later[later.time_local == T("12:00")].rain_15min_mm.isna().all()          # third copy at 12:15 makes 12:00 stuck
    until = live.load_live_readings(live_dir, T("06:00"), {"G"}, stations=None, archive_dir=hist, until=T("12:00"))
    assert until[until.time_local == T("12:00")].rain_15min_mm.tolist() == [25.0]


def test_archive_tail_rows_before_the_first_live_reading_are_not_returned(tmp_path):
    """The runner has the full-history QC for these rows; the tail-QC'd copy must not override it."""
    live_dir, hist = _stuck_setup(tmp_path)
    out = live.load_live_readings(live_dir, T("00:00"), {"G"}, stations=None, archive_dir=hist)
    assert out.time_local.min() >= T("11:45")


def test_no_live_rows_and_no_archive_returns_empty(tmp_path):
    live_dir = tmp_path / "jps_live"
    _write_live_rf(live_dir, [("OTHER", T("11:45"), 5.0), ("OTHER", T("12:00"), 6.0)])
    for archive in (None, tmp_path / "nope"):
        out = live.load_live_readings(live_dir, T("06:00"), {"G"}, stations=None, archive_dir=archive)
        assert out.empty and list(out.columns) == live.COLUMNS


def test_archive_value_wins_over_a_live_placeholder_and_live_fills_archive_gaps(tmp_path):
    live_dir, hist = tmp_path / "jps_live", tmp_path / "jps_hist"
    (live_dir / "wl").mkdir(parents=True)
    pd.DataFrame({"graph_id": "R", "source_time": [T("17:00"), T("17:15")], "wl_m": [0.0, 2.5]}).to_parquet(
        live_dir / "wl" / "2026-10-14.parquet")
    (hist / "wl").mkdir(parents=True)
    pd.DataFrame({"graph_id": "R", "time_local": [T("16:45"), T("17:00"), T("17:15")],
                  "wl_m": [2.4, 2.47, np.nan]}).to_parquet(hist / "wl" / "R.parquet")
    out = live.load_live_readings(live_dir, T("16:00"), {"R"}, stations=None, archive_dir=hist).set_index("time_local")
    assert out.loc[T("17:00"), "wl_m"] == 2.47 and out.loc[T("17:15"), "wl_m"] == 2.5


def test_one_unreadable_archive_file_does_not_abort(tmp_path, caplog):
    live_dir, hist = _stuck_setup(tmp_path)
    (hist / "rf" / "BAD.parquet").write_bytes(b"not parquet")
    with caplog.at_level(logging.WARNING, logger="floodready.live"):
        out = live.load_live_readings(live_dir, T("06:00"), None, stations=None, archive_dir=hist)
    assert out[out.time_local == T("12:00")].rain_15min_mm.isna().all()
    assert any("BAD" in r.getMessage() for r in caplog.records)


def test_missing_archive_warning_is_logged_once_per_process(tmp_path, caplog, monkeypatch):
    monkeypatch.setattr(live, "_warned_no_archive", False)
    live_dir, _ = _stuck_setup(tmp_path)
    with caplog.at_level(logging.WARNING, logger="floodready.live"):
        for _ in range(3):
            live.load_live_readings(live_dir, T("06:00"), {"G"}, stations=None, archive_dir=tmp_path / "nope")
    assert len([r for r in caplog.records if r.name == "floodready.live"]) == 1


def test_tail_covers_the_longest_rule_history():
    assert live.ARCHIVE_TAIL_DAYS >= 40 and live._TAIL_CACHE_DAYS >= live.ARCHIVE_TAIL_DAYS + 5
