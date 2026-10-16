from fastapi.testclient import TestClient

from floodready import radar
from floodready.api.main import create_app


def test_radar_reason_is_shown_in_live_mode_only_and_never_changes_the_level(runner, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "admin@test")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("JWT_SECRET", "test-secret-that-is-at-least-32-bytes-long")
    from datetime import datetime

    from floodready.api import serialize
    fake_now = datetime(2026, 10, 16, 15, 25)   # MYT, whatever the host clock says
    monkeypatch.setattr(serialize, "now_myt", lambda: fake_now)
    seen = []
    reason = radar.to_reason({"direction": "E", "distance_km": 30.0, "eta_min": 45.0})
    runner.ctx.radar = lambda now: seen.append(now) or reason
    with TestClient(create_app(runner, start_live_loop=False)) as client:
        live = client.get("/api/v1/streets/BBR-prone-street").json()
        assert [r["code"] for r in live["reasons"]] == ["radar_approaching"]
        assert live["reasons"][0]["unit"] == "min" and live["reasons"][0]["value"] == 45.0
        assert live["level"] == "normal" and live["trigger_level"] == "normal" and live["fired_by"] == []
        assert seen == [fake_now]
        token = client.post("/api/v1/admin/login", json={"email": "admin@test", "password": "secret"}).json()["token"]
        r = client.post("/api/v1/admin/replay", json={"event": "2024-11-12", "speed": 0, "stop_at": "09:00"},
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        codes = [r["code"] for r in client.get("/api/v1/streets/BBR-prone-street").json()["reasons"]]
        assert "radar_approaching" not in codes
