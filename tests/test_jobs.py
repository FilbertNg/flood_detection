import json
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import requests

from floodready import infobanjir as ib
from floodready import jobs

FIX = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 10, 14, 20, 30)  # MYT


class FixtureSession:
    """Answers each URL with a saved real response and records the requests."""

    def __init__(self, routes):
        self.routes = routes
        self.requests = []

    def get(self, url, params=None, timeout=None):
        self.requests.append((url, dict(params or {})))
        body = self.routes[url]
        response = requests.Response()
        response.status_code = 200
        response._content = (body(params) if callable(body) else body).encode("utf-8")
        response.encoding = "utf-8"
        return response


def fixture(name):
    return (FIX / name).read_text(encoding="utf-8", errors="ignore")


def live_session():
    return FixtureSession({
        ib.WL_LIVE_URL: fixture("infobanjir_wl_live_SEL.html"),
        ib.RF_LIVE_URL: fixture("infobanjir_rf_live_SEL.html"),
    })


# ---------- T2 live logger ----------

def test_jps_live_writes_parsed_rows_and_raw_pages(tmp_path):
    summary = jobs.run_jps_live(live_session(), tmp_path, states=["SEL"], now_local=NOW)
    wl = pd.read_parquet(tmp_path / "jps_live" / "wl" / "2026-10-14.parquet")
    rf = pd.read_parquet(tmp_path / "jps_live" / "rf" / "2026-10-14.parquet")
    assert len(wl) == 67 and len(rf) == summary["rf_rows"]
    binjai = wl[wl.graph_id == "PEKANMERU"].iloc[0]
    assert binjai.wl_m == 3.21 and not binjai.is_stale
    perepat = rf[rf.station_code == "0220301RF"].iloc[0]
    assert json.loads(perepat.daily_mm)["2026-10-10"] == 1.5
    assert len(list((tmp_path / "jps_live" / "html").rglob("*.html.gz"))) == 2


def test_jps_live_is_idempotent_for_the_same_readings(tmp_path):
    jobs.run_jps_live(live_session(), tmp_path, states=["SEL"], now_local=NOW)
    jobs.run_jps_live(live_session(), tmp_path, states=["SEL"], now_local=NOW)
    assert len(pd.read_parquet(tmp_path / "jps_live" / "wl" / "2026-10-14.parquet")) == 67


def test_jps_live_flags_stale_stations_in_summary(tmp_path):
    later = datetime(2026, 10, 15, 3, 0)
    summary = jobs.run_jps_live(live_session(), tmp_path, states=["SEL"], now_local=later)
    assert summary["wl_stale"] == summary["wl_rows"]
    status = json.loads((tmp_path / "jps_live" / "_status.json").read_text())
    assert status["ok"] is False


# ---------- T4 history archive ----------

def history_session():
    def wl(params):
        return fixture("infobanjir_wl_hist_PEKANMERU_20241112.txt")
    return FixtureSession({ib.WL_HIST_URL: wl})


def test_archive_history_caches_chunks_and_skips_them_next_time(tmp_path):
    session = history_session()
    jobs.archive_station_history(session, tmp_path, "PEKANMERU", "wl",
                                 date(2024, 11, 1), date(2024, 11, 30), pause_s=0)
    assert len(session.requests) == 1
    assert session.requests[0][1]["from"] == "01/11/2024 00:00"
    rows = pd.read_parquet(tmp_path / "jps_hist" / "wl" / "PEKANMERU.parquet")
    assert rows.wl_m.max() == 4.26

    jobs.archive_station_history(session, tmp_path, "PEKANMERU", "wl",
                                 date(2024, 11, 1), date(2024, 11, 30), pause_s=0)
    assert len(session.requests) == 1  # cached, not downloaded again


def test_select_archive_stations_puts_named_township_stations_first():
    wl_rows = [
        {"graph_id": "FARAWAY", "district": "Sepang"},
        {"graph_id": "PEKANMERU", "district": "Klang"},
        {"graph_id": "OTHERKLANG", "district": "Klang"},
        {"graph_id": "PERAK1", "district": "Ipoh"},
    ]
    rf_rows = [{"graph_id": "26558", "district": "Klang"}]
    townships = [{"stations": [{"graph_id": "26558"}, {"graph_id": "PEKANMERU"}]}]
    order = jobs.select_archive_stations(wl_rows, rf_rows, townships, districts=["Klang", "Sepang"])
    assert order[:2] == [("26558", "rf"), ("PEKANMERU", "wl")]
    assert ("OTHERKLANG", "wl") in order and ("FARAWAY", "wl") in order
    assert order.index(("OTHERKLANG", "wl")) < order.index(("FARAWAY", "wl"))
    assert ("PERAK1", "wl") not in order


# ---------- T3 warning + forecast loggers ----------

def test_met_warnings_logged_once_per_warning(tmp_path):
    from floodready import met
    session = FixtureSession({met.WARNING_URL: fixture("met_warning.json")})
    jobs.run_met_warnings(session, tmp_path, now_local=NOW)
    jobs.run_met_warnings(session, tmp_path, now_local=NOW)
    rows = pd.read_parquet(tmp_path / "met_warnings" / "2026-10-14.parquet")
    assert len(rows) == 3
    assert "fetched_at_local" in rows.columns


def test_forecast_logger_keeps_every_run(tmp_path):
    from floodready import openmeteo
    session = FixtureSession({openmeteo.FORECAST_URL: fixture("openmeteo_forecast_2pts_2models.json")})
    points = [{"id": "BBR", "lat": 3.06, "lon": 101.47}, {"id": "USJ", "lat": 3.04, "lon": 101.58}]
    models = ["best_match", "gfs_seamless"]
    jobs.run_forecast(session, tmp_path, points, models, now_local=NOW)
    jobs.run_forecast(session, tmp_path, points, models, now_local=datetime(2026, 10, 14, 21, 30))
    rows = pd.read_parquet(tmp_path / "openmeteo_live" / "2026-10-14.parquet")
    assert len(rows) == 2 * (2 * 2 * 6)  # two runs kept, not merged
    assert session.requests[0][1]["models"] == "best_match,gfs_seamless"


def test_rebuild_history_reparses_cached_raw_chunks(tmp_path):
    from floodready import storage
    raw = tmp_path / "jps_hist" / "raw" / "rf" / "26558" / "20241112_20241112.json.gz"
    storage.save_raw(raw, fixture("infobanjir_rf_hist_26558_20241112.txt"))
    stale = pd.DataFrame({"graph_id": ["26558"], "time_local": [datetime(2024, 11, 12, 8, 15)], "rain_15min_mm": [None]})
    out = tmp_path / "jps_hist" / "rf" / "26558.parquet"
    out.parent.mkdir(parents=True)
    stale.to_parquet(out)

    n = jobs.rebuild_history_parquet(tmp_path, "rf", "26558")

    rows = pd.read_parquet(out).set_index("time_local")
    assert n == 96
    assert rows.loc[datetime(2024, 11, 12, 8, 15), "rain_15min_mm"] == 0.0
    assert rows.rain_15min_mm.sum() == 79.0
