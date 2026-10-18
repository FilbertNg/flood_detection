import pytest
from fastapi.testclient import TestClient

from floodready import push
from floodready.api.main import create_app
from floodready.api.runner import Runner
from floodready.db import repo

DEV = "device-0000000001"
BODY = {"device_id": DEV, "lang": "ms", "street_ids": ["BBR-prone-street"],
        "subscription": {"endpoint": "https://fcm.googleapis.com/fcm/send/abc", "expirationTime": None, "keys": {"p256dh": "BPk_-1", "auth": "aB_-9"}}}


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
    assert [(s["device_id"], s["lang"], s["endpoint"]) for s in subs] == [(DEV, "ms", "https://fcm.googleapis.com/fcm/send/abc")]
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
        repo.insert_answer(c, {"device_id": DEV, "alert_id": None, "street_id": "BBR-prone-street",
                               "answer": "report", "photo_path": str(photo)})
    assert client.delete(f"/api/v1/subscriptions/{DEV}").status_code == 204
    assert not photo.exists()
    with runner.db.begin() as c:
        assert repo.list_subscribers(c, "BBR-prone-street") == [] and repo.list_answers(c) == []
    assert client.delete(f"/api/v1/subscriptions/{DEV}").status_code == 204   # idempotent


def sub(**over):
    base = BODY["subscription"]
    return {**BODY, "subscription": {**base, **over}}


@pytest.mark.parametrize("endpoint", [
    "http://fcm.googleapis.com/fcm/send/x", "http://127.0.0.1:22/", "file:///etc/passwd", "https://127.0.0.1/x",
    "https://evil.example.com/push", "https://fcm.googleapis.com.evil.com/x", "https://user@evil.com@fcm.googleapis.com/x",
    "https://fcm.googleapis.com:8443/x", "ftp://fcm.googleapis.com/x", "https://" + "a" * 2100 + ".notify.windows.com/x"])
def test_bad_or_foreign_endpoints_are_rejected(client, endpoint):
    assert client.post("/api/v1/subscriptions", json=sub(endpoint=endpoint)).status_code == 422


@pytest.mark.parametrize("endpoint", [
    "https://fcm.googleapis.com/fcm/send/x", "https://updates.push.services.mozilla.com/wpush/v2/x",
    "https://wns2-par02p.notify.windows.com/w/?token=x", "https://web.push.apple.com/QL", "https://api.push.apple.com/3/device/x"])
def test_push_service_hosts_are_accepted(client, endpoint):
    assert client.post("/api/v1/subscriptions", json=sub(endpoint=endpoint)).status_code == 204


def test_oversized_malformed_and_extra_keys_are_rejected(client):
    ok = {"p256dh": "BPk_-1", "auth": "aB_-9"}
    for keys in [{**ok, "p256dh": "A" * 129}, {**ok, "auth": "A" * 65}, {**ok, "junk": "x"}, {"p256dh": "A" * 100000, "auth": "a"},
                 {**ok, "auth": "not base64!"}, {**ok, "p256dh": ""}, {"p256dh": "x"}]:
        assert client.post("/api/v1/subscriptions", json=sub(keys=keys)).status_code == 422, keys
    assert client.post("/api/v1/subscriptions", json={**BODY, "extra": 1}).status_code == 422


@pytest.mark.parametrize("device_id", ["dev-1", "short", "x" * 65, "has space 0123456789", "bad/char/0123456789", ""])
def test_device_id_must_match_the_pattern(client, device_id):
    assert client.post("/api/v1/subscriptions", json={**BODY, "device_id": device_id}).status_code == 422
