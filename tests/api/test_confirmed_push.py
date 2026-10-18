"""WP4 + WP3: "Confirmed by neighbours" push end to end, and rehearsal cleanup of demo answers."""
import json
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from floodready import push
from floodready.api.main import create_app
from floodready.api.runner import Runner
from floodready.db import repo
from floodready.jobs import now_myt
from tests.api.test_answers import API, STREET, jpeg, make_alert

KEYS = {"p256dh": "k", "auth": "a"}


@pytest.fixture()
def env(context, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("SENSOR_TOKEN", "tok")
    monkeypatch.setattr(repo, "sensor_devices", lambda: {"sim-1": {STREET}, "real-1": {STREET}})
    sent = []
    db = repo.connect("sqlite://")
    runner = Runner(context, db=db, push=push.PushService(db, send=lambda sub, data: sent.append((sub["device_id"], json.loads(data))),
                                                          public_key="pub"))
    with TestClient(create_app(runner, start_live_loop=False)) as client:
        yield type("Env", (), {"client": client, "runner": runner, "db": db, "sent": sent, "uploads": tmp_path / "uploads"})


def subscribe(env, device, lang="en", street=STREET):
    with env.db.begin() as c:
        repo.upsert_subscription(c, device, {"endpoint": f"https://fcm.googleapis.com/{device}", "keys": KEYS}, [street], lang)


def answer(env, device, alert_id, kind="yes", **kw):
    return env.client.post(f"{API}/answers", data={"device_id": device, "street_id": STREET, "answer": kind,
                                                   "alert_id": alert_id, **kw})


def live_alert(env, **kw):
    replay = kw.pop("is_replay", False)
    with env.db.begin() as c:
        return repo.insert_alerts(c, [make_alert(**kw)], is_replay=replay, is_backfill=False)[0]


def test_confirmation_sends_one_follow_up_to_the_street_in_each_language(env):
    subscribe(env, "dev-a", "en")
    subscribe(env, "dev-b", "ms")
    subscribe(env, "dev-other", street="BBR-safe-street")
    aid = live_alert(env)
    answer(env, "dev-a", aid)
    env.runner.push.flush()
    assert env.sent == []
    answer(env, "dev-b", aid)
    answer(env, "dev-c", aid)                       # a third yes does not send again
    env.runner.push.flush()
    by_device = {d: p for d, p in env.sent}
    assert set(by_device) == {"dev-a", "dev-b"} and len(env.sent) == 2
    assert by_device["dev-a"]["title"] == f"Confirmed by neighbours: Prone Street"
    assert by_device["dev-b"]["title"] == "Disahkan oleh jiran: Prone Street"
    assert by_device["dev-a"]["alert_id"] == aid and by_device["dev-a"]["url"] == f"/street/{STREET}"


def test_replay_follow_up_is_prefixed(env):
    subscribe(env, "dev-a")
    aid = live_alert(env, is_replay=True)
    answer(env, "dev-a", aid)
    answer(env, "dev-b", aid)
    env.runner.push.flush()
    assert [p["title"] for _, p in env.sent] == ["[Replay] Confirmed by neighbours: Prone Street"]


def test_no_follow_up_for_a_non_push_alert(env):
    from floodready.engine.types import Level
    subscribe(env, "dev-a")
    with env.db.begin() as c:
        aid = repo.insert_alerts(c, [make_alert(level=Level.NORMAL)], is_replay=False, is_backfill=False)[0]
    answer(env, "dev-a", aid)
    answer(env, "dev-b", aid)
    env.runner.push.flush()
    assert env.sent == []


def test_real_sensor_confirmation_pushes_but_simulated_does_not(env):
    subscribe(env, "dev-a")
    live_alert(env, at=now_myt().replace(microsecond=0) - timedelta(minutes=10))
    h = {"Authorization": "Bearer tok"}
    env.client.post(f"{API}/sensor/readings", json={"device_id": "sim-1", "level_cm": 60, "simulated": True}, headers=h)
    env.runner.push.flush()
    assert env.sent == []
    env.client.post(f"{API}/sensor/readings", json={"device_id": "real-1", "level_cm": 60, "simulated": False}, headers=h)
    env.runner.push.flush()
    assert len(env.sent) == 1 and env.sent[0][1]["title"].startswith("Confirmed by neighbours")


def test_the_request_does_not_wait_for_the_push(env):
    import threading
    gate = threading.Event()
    env.runner.push._send = lambda sub, data: gate.wait(5)
    subscribe(env, "dev-a")
    aid = live_alert(env)
    answer(env, "dev-a", aid)
    assert answer(env, "dev-b", aid).status_code == 200      # returns while the worker is still blocked
    gate.set()
    env.runner.push.flush()


def test_two_rehearsals_in_a_row_start_unconfirmed_and_the_same_devices_can_answer(env):
    body = {"event": "2024-11-12", "speed": 0, "stop_at": "09:00"}
    env.runner.start_replay(__import__("datetime").date(2024, 11, 12), speed=None, start="06:00", end="14:00", stop_at="09:00")
    for rehearsal in range(2):
        alert = next(a for a in env.client.get(f"{API}/alerts").json() if a["street_id"] == STREET and a["kind"] == "alert")
        assert alert["outcome"] == "unverified", f"rehearsal {rehearsal} starts unconfirmed"
        assert answer(env, "demo-1", alert["alert_id"], photo=None).status_code == 200
        assert answer(env, "demo-2", alert["alert_id"]).status_code == 200
        assert env.client.post(f"{API}/answers", data={"device_id": "demo-1", "street_id": STREET, "answer": "report"},
                               files={"photo": ("p.jpg", jpeg(), "image/jpeg")}).status_code == 200
        shown = next(a for a in env.client.get(f"{API}/alerts").json() if a["alert_id"] == alert["alert_id"])
        assert shown["outcome"] == "confirmed"
        assert len(list(env.uploads.iterdir())) == 1
        env.runner.start_replay(__import__("datetime").date(2024, 11, 12), speed=None, start="06:00", end="14:00", stop_at="09:00")
        assert not env.uploads.exists() or list(env.uploads.iterdir()) == []      # demo photos removed after the commit
    del body
