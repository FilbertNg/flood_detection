import pandas as pd
import pytest
from fastapi.testclient import TestClient

from floodready.api.main import create_app

STREET_DETAIL_KEYS = {"street_id", "name", "township_id", "susceptibility", "level", "trigger_level", "confidence",
                      "flood_probability", "fired_by", "window", "reasons", "data_time", "rain_next_12h", "tide",
                      "river_forecast", "stations", "active_alert", "history", "is_replay"}


@pytest.fixture()
def client(runner, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "admin@test")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("JWT_SECRET", "test-secret-that-is-at-least-32-bytes-long")
    with TestClient(create_app(runner, start_live_loop=False)) as c:
        yield c


def login(client):
    r = client.post("/api/v1/admin/login", json={"email": "admin@test", "password": "secret"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def replay_until(client, hhmm):
    r = client.post("/api/v1/admin/replay", json={"event": "2024-11-12", "speed": 0, "stop_at": hhmm}, headers=login(client))
    assert r.status_code == 200, r.text
    return r.json()


def test_admin_endpoints_need_a_token(client):
    assert client.post("/api/v1/admin/replay", json={"event": "2024-11-12", "speed": 0}).status_code == 401
    assert client.post("/api/v1/admin/login", json={"email": "admin@test", "password": "wrong"}).status_code == 401


def test_status_reports_replay_mode(client):
    status = replay_until(client, "09:00")
    assert status["mode"] == "replay" and status["replay"]["event"] == "2024-11-12"
    assert status["data_time"] == "2024-11-12T09:00:00+08:00"


def test_streets_are_geojson_with_contract_properties(client):
    replay_until(client, "09:00")
    fc = client.get("/api/v1/streets", params={"township": "BBR"}).json()
    assert fc["type"] == "FeatureCollection" and len(fc["features"]) == 2
    props = {f["properties"]["street_id"]: f["properties"] for f in fc["features"]}
    assert set(props["BBR-prone-street"]) == {"street_id", "name", "township_id", "susceptibility", "level", "updated_at"}
    assert props["BBR-prone-street"]["level"] == "warning" and props["BBR-safe-street"]["level"] == "normal"
    assert fc["features"][0]["geometry"]["type"] == "LineString"


def test_street_detail_matches_the_contract(client):
    replay_until(client, "09:00")
    d = client.get("/api/v1/streets/BBR-prone-street").json()
    assert set(d) == STREET_DETAIL_KEYS
    assert d["level"] == "warning" and d["is_replay"] is True
    assert d["window"] == {"start": "2024-11-12T09:30:00+08:00", "end": "2024-11-12T10:30:00+08:00"}
    assert d["reasons"][0]["text"] == {"en": "61.5 mm of rain in 1 h at Kg. Perepat, Kapar",
                                       "ms": "Hujan 61.5 mm dalam 1 jam di Kg. Perepat, Kapar"}
    assert d["active_alert"]["level"] == "warning"
    assert client.get("/api/v1/streets/BBR-nope").status_code == 404


def test_stations_and_series(client):
    replay_until(client, "10:00")
    stations = {s["graph_id"] + s["kind"]: s for s in client.get("/api/v1/stations", params={"township": "BBR"}).json()}
    pm = stations["PEKANMERUwl"]
    assert pm["thresholds"] == {"alert": 3.8, "warning": 4.0, "danger": 4.2} and pm["latest"]["wl_m"] == 4.21
    series = client.get("/api/v1/stations/PEKANMERU/series", params={"from": "2024-11-12T09:30:00+08:00",
                                                                      "to": "2024-11-12T10:00:00+08:00"}).json()
    assert [p["wl_m"] for p in series if p["wl_m"] is not None] == [4.06, 4.16, 4.21]


def test_alerts_for_a_street(client):
    replay_until(client, "10:00")
    alerts = client.get("/api/v1/alerts", params={"street_id": "BBR-prone-street"}).json()
    assert [a["level"] for a in alerts] == ["danger", "warning", "watch"]   # newest first; Watch is an alert level
    assert alerts[0]["window"]["start"] == "2024-11-12T10:30:00+08:00"


def test_street_detail_lists_the_streets_own_stations_river_first(runner, client):
    runner.ctx.street_stations = {"BBR-prone-street": {"wl": "PEKANMERU", "rf": ["26558"], "method": "flow", "distance_m": 5.0},
                                  "BBR-safe-street": {"wl": None, "rf": ["KGRANTAUPANJANG", "TELOKGONG"], "method": None, "distance_m": None}}
    replay_until(client, "09:30")
    assert client.get("/api/v1/streets/BBR-prone-street").json()["stations"] == ["PEKANMERU", "26558"]
    safe = client.get("/api/v1/streets/BBR-safe-street").json()
    assert safe["stations"] == ["KGRANTAUPANJANG", "TELOKGONG"] and safe["level"] == "normal"
    assert client.get("/api/v1/streets/BBR-prone-street").json()["level"] == "warning"


def test_street_detail_without_a_mapping_lists_the_township_stations(client):
    replay_until(client, "09:00")
    assert len(client.get("/api/v1/streets/BBR-prone-street").json()["stations"]) == 7


def test_street_detail_river_forecast_is_null_without_a_model(client):
    replay_until(client, "09:00")
    assert client.get("/api/v1/streets/BBR-prone-street").json()["river_forecast"] is None


def test_a_failing_forecast_does_not_break_the_street_page(client, runner):
    def boom(*a):
        raise KeyError("['n_rf_10km'] not in index")

    runner.ctx.river_forecast = boom
    replay_until(client, "09:00")
    r = client.get("/api/v1/streets/BBR-prone-street")
    assert r.status_code == 200 and r.json()["river_forecast"] is None


def test_street_detail_uses_the_station_closest_to_warning_with_a_fresh_reading(client, runner):
    seen = []
    runner.ctx.river_forecast = lambda readings, gid, at, live: seen.append(gid) or {
        "graph_id": gid, "wl_now_m": 3.5, "wl_now_time": "2024-11-12T09:00:00+08:00", "warning_m": 4.0, "points": []}
    replay_until(client, "09:00")
    d = client.get("/api/v1/streets/BBR-prone-street").json()
    assert seen[-1] == "PEKANMERU"              # 26558 reads a flat, stuck level on 12 Nov 2024
    assert d["river_forecast"]["name"] == "Sg. Binjai di Pekan Meru"


def _blank_wl(runner, graph_id):
    real = runner.ctx.load_readings

    def load(start, end):
        df = real(start, end).copy()
        df.loc[(df.graph_id == graph_id) & (df.kind == "wl"), "wl_m"] = float("nan")
        return df
    runner.ctx.load_readings = load


def test_river_forecast_follows_the_first_live_candidate(runner, client):
    seen = []
    runner.ctx.river_forecast = lambda readings, gid, at, live: seen.append(gid) or {
        "graph_id": gid, "wl_now_m": 3.5, "wl_now_time": "2024-11-12T09:00:00+08:00", "warning_m": 4.0, "points": []}
    runner.ctx.street_stations = {"BBR-prone-street": {"wl": "26558", "wl_candidates": ["26558", "PEKANMERU"], "rf": [],
                                                       "method": "flow", "distance_m": 5.0}}
    _blank_wl(runner, "26558")                       # QC has blanked the dead gauge
    replay_until(client, "09:00")
    d = client.get("/api/v1/streets/BBR-prone-street").json()
    assert seen[-1] == "PEKANMERU" and d["river_forecast"]["name"] == "Sg. Binjai di Pekan Meru"


def test_river_forecast_is_null_when_every_candidate_is_dead(runner, client):
    seen = []
    runner.ctx.river_forecast = lambda readings, gid, at, live: seen.append(gid) or {"graph_id": gid}
    runner.ctx.street_stations = {"BBR-prone-street": {"wl": "26558", "wl_candidates": ["26558"], "rf": [],
                                                       "method": "flow", "distance_m": 5.0}}
    _blank_wl(runner, "26558")
    replay_until(client, "09:00")
    assert client.get("/api/v1/streets/BBR-prone-street").json()["river_forecast"] is None
    assert seen == []                                # no township-wide borrow either


def test_river_forecast_keeps_the_first_candidate_while_it_is_alive(runner, client):
    seen = []
    runner.ctx.river_forecast = lambda readings, gid, at, live: seen.append(gid) or {
        "graph_id": gid, "wl_now_m": 3.5, "wl_now_time": "2024-11-12T09:00:00+08:00", "warning_m": 4.0, "points": []}
    runner.ctx.street_stations = {"BBR-prone-street": {"wl": "PANDAMARAN", "wl_candidates": ["PANDAMARAN", "PEKANMERU"],
                                                       "rf": [], "method": "flow", "distance_m": 5.0}}
    replay_until(client, "09:00")
    client.get("/api/v1/streets/BBR-prone-street")
    assert seen[-1] == "PANDAMARAN"


def test_river_forecast_uses_the_streets_own_station_and_falls_back_to_the_pick(runner, client):
    seen = []
    runner.ctx.river_forecast = lambda readings, gid, at, live: seen.append(gid) or {
        "graph_id": gid, "wl_now_m": 3.5, "wl_now_time": "2024-11-12T09:00:00+08:00", "warning_m": 4.0, "points": []}
    runner.ctx.street_stations = {"BBR-prone-street": {"wl": "PANDAMARAN", "rf": [], "method": "flow", "distance_m": 5.0},
                                  "BBR-safe-street": {"wl": None, "rf": ["TELOKGONG"], "method": None, "distance_m": None}}
    replay_until(client, "09:00")
    own = client.get("/api/v1/streets/BBR-prone-street").json()["river_forecast"]
    assert seen[-1] == "PANDAMARAN" and own["graph_id"] == "PANDAMARAN"
    client.get("/api/v1/streets/BBR-safe-street")
    assert seen[-1] == "PEKANMERU"                  # no station of its own: nearest to warning with a fresh reading


def test_street_detail_tide_points_flag_harmonic_fill(runner, client):
    times = pd.date_range("2024-11-12 08:00", periods=14, freq="h")
    runner.ctx.tide = pd.DataFrame({"time_local": times, "tide_height_m": [1.0 + 0.1 * i for i in range(14)],
                                    "tide_filled": [i in (3, 4) for i in range(14)]})
    replay_until(client, "09:00")
    tide = client.get("/api/v1/streets/BBR-prone-street").json()["tide"]
    assert tide and all(set(p) == {"time", "height_m", "filled"} for p in tide)
    by_time = {p["time"]: p["filled"] for p in tide}
    assert by_time["2024-11-12T11:00:00+08:00"] is True and by_time["2024-11-12T12:00:00+08:00"] is True
    assert by_time["2024-11-12T10:00:00+08:00"] is False and by_time["2024-11-12T13:00:00+08:00"] is False


def test_street_detail_tide_without_a_filled_column_is_not_flagged(runner, client):
    times = pd.date_range("2024-11-12 08:00", periods=6, freq="h")
    runner.ctx.tide = pd.DataFrame({"time_local": times, "tide_height_m": [1.0] * 6})
    replay_until(client, "09:00")
    tide = client.get("/api/v1/streets/BBR-prone-street").json()["tide"]
    assert tide and all(p["filled"] is False for p in tide)
