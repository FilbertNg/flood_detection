import json
from datetime import date, datetime

from fastapi.testclient import TestClient

from floodready import push
from floodready.api.main import create_app
from floodready.api.runner import Runner
from floodready.db import repo

SUB = {"endpoint": "https://push.example/1", "keys": {"p256dh": "P", "auth": "A"}}
D = date(2024, 11, 12)


def make(context, url="sqlite://"):
    eng = repo.connect(url)
    with eng.begin() as c:
        repo.upsert_subscription(c, "dev", SUB, ["BBR-prone-street"], "en")
    sent = []
    svc = push.PushService(eng, send=lambda s, d: sent.append(json.loads(d)), public_key="k")
    return Runner(context, db=eng, push=svc), sent, svc


def test_replay_persists_states_and_alerts_and_pushes_with_replay_prefix(context):
    r, sent, svc = make(context)
    r.start_replay(D, speed=None, start="06:00", end="14:00")
    svc.flush()
    with r.db.begin() as c:
        assert {s["street_id"] for s in repo.get_street_states(c, "BBR", "replay")} == {"BBR-prone-street", "BBR-safe-street"}
        assert len(repo.list_alerts(c)) == len(r.snapshot().alerts) > 0
    assert sent and all(p["title"].startswith("[Replay] ") for p in sent)
    assert all(p["url"] == "/street/BBR-prone-street" for p in sent)


def test_only_push_levels_are_pushed_never_all_clear(context):
    r, sent, svc = make(context)
    r.start_replay(D, speed=None, start="06:00", end="14:00")
    svc.flush()
    mine = [a for a in r.snapshot().alerts if a["street_id"] == "BBR-prone-street"]
    assert sorted(p["alert_id"] for p in sent) == sorted(a["alert_id"] for a in mine if a["push"])
    assert not any(p["alert_id"].endswith("all_clear") for p in sent)


def test_two_replays_in_a_row_both_push(context):
    r, sent, svc = make(context)
    r.start_replay(D, speed=None, start="06:00", end="14:00")
    svc.flush()
    first = len(sent)
    assert first > 0
    r.start_replay(D, speed=None, start="06:00", end="14:00")
    svc.flush()
    assert len(sent) == 2 * first
    with r.db.begin() as c:
        assert len(repo.list_alerts(c)) == len(r.snapshot().alerts)


def test_restart_keeps_alerts_and_does_not_repush(context, tmp_path):
    url = f"sqlite:///{(tmp_path / 'f.db').as_posix()}"
    now = datetime(2024, 11, 12, 9, 0)
    r, sent, svc = make(context, url)
    r.refresh_live(now)
    svc.flush()
    stored = r.snapshot().alerts
    assert stored and not any(a["is_replay"] for a in stored) and sent
    r2, sent2, svc2 = make(context, url)                       # "restart": new process, same database
    assert r2.snapshot().alerts == stored
    r2.refresh_live(now)
    svc2.flush()
    assert sent2 == [] and r2.snapshot().alerts == stored


def test_stop_replay_clears_replay_alerts_and_states(context):
    r, sent, svc = make(context)
    r.start_replay(D, speed=None, start="06:00", end="14:00")
    r.stop_replay()
    assert r.snapshot().alerts == []
    with r.db.begin() as c:
        assert repo.list_alerts(c) == [] and repo.get_street_states(c, "BBR", "replay") == []


def test_get_alerts_and_street_history_read_the_db(context):
    r, sent, svc = make(context)
    with TestClient(create_app(r, start_live_loop=False)) as client:
        r.start_replay(D, speed=None, start="06:00", end="14:00")
        with r.db.begin() as c:
            expected = repo.list_alerts(c, street_id="BBR-prone-street")
            active = repo.list_alerts(c, active=True)
        assert client.get("/api/v1/alerts", params={"street_id": "BBR-prone-street"}).json() == expected
        assert client.get("/api/v1/alerts", params={"active": "true"}).json() == active
        assert client.get("/api/v1/streets/BBR-prone-street").json()["history"] == expected[:10]


def test_an_all_clear_is_stored_but_not_pushed(context):
    from floodready.engine.replay import ReplayStep
    from floodready.engine.types import Alert, Level
    r, sent, svc = make(context)
    t = datetime(2024, 11, 12, 12, 0)
    clear = Alert("BBR-prone-street", Level.NORMAL, "all_clear", t, None, None, (), ())
    r._record(ReplayStep(time=t, trigger=None, states=[], alerts=[clear]), is_replay=False)
    svc.flush()
    assert [a["kind"] for a in r.snapshot().alerts] == ["all_clear"] and sent == []


def live_warning(r, level=None):
    from floodready.engine.replay import ReplayStep
    from floodready.engine.types import Alert, Level
    from tests.db.test_repo import state
    t = datetime(2026, 10, 18, 9, 0)
    level = level or Level.WARNING
    a = Alert("BBR-prone-street", level, "alert", t, None, None, (), ("rule_rain",))
    r._record(ReplayStep(time=t, trigger=None, states=[state("BBR-prone-street", level)], alerts=[a]), is_replay=False)


def test_replay_mode_shows_replay_rows_only_even_with_a_live_alert(context):
    r, sent, svc = make(context)
    with TestClient(create_app(r, start_live_loop=False)) as client:
        live_warning(r)
        r.start_replay(D, speed=None, start="06:00", end="14:00", stop_at="09:00")
        alerts = client.get("/api/v1/alerts").json()
        assert alerts and all(a["is_replay"] for a in alerts)
        active = client.get("/api/v1/alerts", params={"active": "true"}).json()
        assert len({a["street_id"] for a in active}) == len(active)
        detail = client.get("/api/v1/streets/BBR-prone-street").json()
        assert detail["history"] and all(h["is_replay"] for h in detail["history"])
        assert detail["active_alert"]["alert_id"].endswith("~replay")
        r.stop_replay()          # back to live: the live alert is visible again, no replay rows
        detail = client.get("/api/v1/streets/BBR-prone-street").json()
        assert [h["is_replay"] for h in detail["history"]] == [False]


def test_a_live_alert_without_an_all_clear_is_not_active_once_the_street_is_normal(context):
    from floodready.engine.types import Level
    r, sent, svc = make(context)
    with TestClient(create_app(r, start_live_loop=False)) as client:
        live_warning(r)
        assert len(client.get("/api/v1/alerts", params={"active": "true"}).json()) == 1
        with r.db.begin() as c:                       # the street recovered while the all-clear was never issued
            from tests.db.test_repo import state
            repo.save_street_states(c, [state("BBR-prone-street", Level.NORMAL)], "live")
        assert client.get("/api/v1/alerts", params={"active": "true"}).json() == []


def test_snapshot_does_not_query_alerts_until_they_are_read(context, monkeypatch):
    r, sent, svc = make(context)
    calls = []
    real = repo.list_alerts
    monkeypatch.setattr(repo, "list_alerts", lambda *a, **k: calls.append(1) or real(*a, **k))
    snap = r.snapshot()
    with TestClient(create_app(r, start_live_loop=False)) as client:
        client.get("/api/v1/status")
        client.get("/api/v1/streets")
    assert calls == []
    assert snap.alerts == [] and calls == [1]
