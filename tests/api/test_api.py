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
    assert [a["level"] for a in alerts] == ["danger", "warning"]   # newest first
    assert alerts[0]["window"]["start"] == "2024-11-12T10:30:00+08:00"
