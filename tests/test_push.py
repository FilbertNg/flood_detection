import json
import logging

import pytest

from floodready import push
from floodready.db import repo


def SUB(n):
    return {"endpoint": f"https://push.example/{n}", "keys": {"p256dh": f"p{n}", "auth": f"a{n}"}}


def summary(level="warning", kind="alert", is_replay=False, sid="BBR-a"):
    return {"alert_id": f"{sid}@20241112T0900-{kind}", "street_id": sid, "horizon": "nowcast", "kind": kind,
            "level": level, "issued_at": "2024-11-12T09:00:00+08:00", "window": None, "outcome": "unverified",
            "is_replay": is_replay, "push": kind == "alert"}


class Failed(Exception):
    def __init__(self, status):
        self.response = type("R", (), {"status_code": status})()


@pytest.fixture
def conn():
    eng = repo.connect("sqlite://")
    with eng.begin() as c:
        repo.upsert_subscription(c, "en1", SUB("en1"), ["BBR-a"], "en")
        repo.upsert_subscription(c, "ms1", SUB("ms1"), ["BBR-a", "BBR-b"], "ms")
        repo.upsert_subscription(c, "other", SUB("other"), ["BBR-b"], "en")
        yield c


def test_payload_is_exactly_push_payload_and_localised():
    en = push.payload(summary("danger"), "Jalan Makyong", "en")
    assert set(en) == {"title", "body", "url", "alert_id", "level"}
    assert en["url"] == "/street/BBR-a" and en["level"] == "danger" and "Jalan Makyong" in en["title"]
    ms = push.payload(summary("danger"), "Jalan Makyong", "ms")
    assert ms["title"] != en["title"] and "Jalan Makyong" in ms["title"]


def test_replay_title_is_prefixed():
    assert push.payload(summary(is_replay=True), "J", "en")["title"].startswith("[Replay] ")
    assert push.payload(summary(is_replay=True), "J", "ms")["title"].startswith("[Replay] ")
    assert not push.payload(summary(), "J", "en")["title"].startswith("[Replay]")


def test_notify_sends_only_to_street_subscribers_in_their_language(conn):
    sent = []
    n = push.notify(conn, summary(), "Jalan A", send=lambda sub, data: sent.append((sub["endpoint"], data)))
    assert n == 2
    by = {e: json.loads(d) for e, d in sent}
    assert set(by) == {"https://push.example/en1", "https://push.example/ms1"}
    assert by["https://push.example/en1"]["title"] != by["https://push.example/ms1"]["title"]


def test_notify_does_not_push_all_clear_or_flag_false(conn):
    sent = []

    def send(sub, data):
        sent.append(1)
    assert push.notify(conn, summary(kind="all_clear"), "A", send=send) == 0
    assert push.notify(conn, {**summary(), "push": False}, "A", send=send) == 0
    assert sent == []


@pytest.mark.parametrize("status", [404, 410])
def test_gone_subscription_is_deleted(conn, status):
    def send(sub, data):
        if sub["endpoint"].endswith("en1"):
            raise Failed(status)
    assert push.notify(conn, summary(), "A", send=send) == 1
    assert [s["device_id"] for s in repo.list_subscribers(conn, "BBR-a")] == ["ms1"]


def test_other_errors_are_logged_and_do_not_stop_the_rest(conn, caplog):
    def send(sub, data):
        if sub["endpoint"].endswith("en1"):
            raise Failed(500)
    with caplog.at_level(logging.WARNING):
        assert push.notify(conn, summary(), "A", send=send) == 1
    assert len(repo.list_subscribers(conn, "BBR-a")) == 2     # a 500 keeps the subscription
    assert "push failed" in caplog.text


def test_missing_keys_disable_push_with_one_warning(monkeypatch, caplog):
    for k in ("VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY", "VAPID_SUBJECT"):
        monkeypatch.delenv(k, raising=False)
    with caplog.at_level(logging.WARNING):
        svc = push.PushService(repo.connect("sqlite://"))
        svc.enqueue([summary()], {})
        svc.enqueue([summary()], {})
    assert not svc.enabled and svc.public_key is None
    assert caplog.text.count("push disabled") == 1


def test_service_reads_keys_from_env(monkeypatch):
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "pub")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "priv")
    monkeypatch.setenv("VAPID_SUBJECT", "mailto:a@b.c")
    svc = push.PushService(repo.connect("sqlite://"))
    assert svc.enabled and svc.public_key == "pub"


def test_service_sends_in_background_and_flush_waits():
    eng = repo.connect("sqlite://")
    with eng.begin() as c:
        repo.upsert_subscription(c, "d", SUB("d"), ["BBR-a"], "en")
    sent = []
    svc = push.PushService(eng, send=lambda s, d: sent.append(d), public_key="k")
    svc.enqueue([summary()], {"BBR-a": "Jalan A"})
    svc.flush()
    assert len(sent) == 1


def test_make_sender_calls_pywebpush_with_vapid(monkeypatch):
    import pywebpush
    calls = []
    monkeypatch.setattr(pywebpush, "webpush", lambda **kw: calls.append(kw))
    push.make_sender("PRIV", "mailto:a@b.co")({"endpoint": "https://e", "p256dh": "P", "auth": "A"}, "{}")
    kw = calls[0]
    assert kw["subscription_info"] == {"endpoint": "https://e", "keys": {"p256dh": "P", "auth": "A"}}
    assert kw["vapid_private_key"] == "PRIV" and kw["vapid_claims"] == {"sub": "mailto:a@b.co"} and kw["timeout"] > 0


def test_logs_never_contain_the_raw_device_id(conn, caplog):
    def send(sub, data):
        raise Failed(500 if sub["device_id"] == "en1" else 410)
    with caplog.at_level(logging.INFO):
        push.notify(conn, summary(), "A", send=send)
    assert "en1" not in caplog.text and "ms1" not in caplog.text and push.device_tag("en1") in caplog.text


def test_no_database_connection_is_held_while_sending(tmp_path):
    eng = repo.connect(f"sqlite:///{(tmp_path / 'p.db').as_posix()}")
    with eng.begin() as c:
        repo.upsert_subscription(c, "d1", SUB("d1"), ["BBR-a"], "en")
        repo.upsert_subscription(c, "d2", SUB("d2"), ["BBR-a"], "en")
    held = []

    def send(sub, data):
        held.append(eng.pool.checkedout())
        if sub["device_id"] == "d1":
            raise Failed(410)
    svc = push.PushService(eng, send=send, public_key="k")
    svc.enqueue([summary()], {})
    svc.flush()
    assert held == [0, 0]
    with eng.begin() as c:
        assert [s["device_id"] for s in repo.list_subscribers(c, "BBR-a")] == ["d2"]
