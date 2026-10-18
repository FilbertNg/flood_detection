import pytest
from fastapi.testclient import TestClient

from floodready import push
from floodready.api.main import create_app
from floodready.api.runner import Runner
from floodready.db import repo

BODY = {"device_id": "dev-1", "lang": "ms", "street_ids": ["BBR-prone-street"],
        "subscription": {"endpoint": "https://push.example/1", "expirationTime": None, "keys": {"p256dh": "P", "auth": "A"}}}


@pytest.fixture()
def runner(context, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path / "up"))
    eng = repo.connect("sqlite://")
    return Runner(context, db=eng, push=push.PushService(eng, send=lambda s, d: None, public_key="PUBKEY"))


@pytest.fixture()
def client(runner):
    with TestClient(create_app(runner, start_live_loop=False)) as c:
        yield c


def test_public_key(client):
    r = client.get("/api/v1/push/public-key")
    assert r.status_code == 200 and r.json() == {"key": "PUBKEY"}


def test_public_key_503_when_push_disabled(context, monkeypatch):
    for k in ("VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY", "VAPID_SUBJECT"):
        monkeypatch.delenv(k, raising=False)
    with TestClient(create_app(Runner(context), start_live_loop=False)) as c:
        assert c.get("/api/v1/push/public-key").status_code == 503
        assert c.post("/api/v1/subscriptions", json=BODY).status_code == 204    # storing is fine; sending is off


def test_subscribe_stores_device_and_streets(client, runner):
    assert client.post("/api/v1/subscriptions", json=BODY).status_code == 204
    with runner.db.begin() as c:
        subs = repo.list_subscribers(c, "BBR-prone-street")
    assert [(s["device_id"], s["lang"], s["endpoint"]) for s in subs] == [("dev-1", "ms", "https://push.example/1")]
    client.post("/api/v1/subscriptions", json={**BODY, "street_ids": ["BBR-safe-street"]})   # replaces the street list
    with runner.db.begin() as c:
        assert repo.list_subscribers(c, "BBR-prone-street") == []
        assert len(repo.list_subscribers(c, "BBR-safe-street")) == 1


def test_unknown_street_and_bad_lang_are_rejected(client):
    assert client.post("/api/v1/subscriptions", json={**BODY, "street_ids": ["BBR-nope"]}).status_code == 400
    assert client.post("/api/v1/subscriptions", json={**BODY, "lang": "fr"}).status_code == 422


def test_delete_removes_device_rows_then_photo_files(client, runner, tmp_path):
    up = tmp_path / "up"
    up.mkdir()
    photo = up / "p.jpg"
    photo.write_bytes(b"x")
    client.post("/api/v1/subscriptions", json=BODY)
    with runner.db.begin() as c:
        repo.insert_answer(c, {"device_id": "dev-1", "alert_id": None, "street_id": "BBR-prone-street",
                               "answer": "report", "photo_path": str(photo)})
    assert client.delete("/api/v1/subscriptions/dev-1").status_code == 204
    assert not photo.exists()
    with runner.db.begin() as c:
        assert repo.list_subscribers(c, "BBR-prone-street") == [] and repo.list_answers(c) == []
    assert client.delete("/api/v1/subscriptions/dev-1").status_code == 204   # idempotent
