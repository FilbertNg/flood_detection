import sqlite3
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from floodready.db import repo, schema
from floodready.engine.types import Alert, Level, Reason, StreetState

T0 = datetime(2024, 11, 12, 9, 0)


@pytest.fixture
def conn():
    eng = repo.connect("sqlite://")
    with eng.begin() as c:
        yield c


def reason(code="rain_1h"):
    return Reason(code, 45.5, "mm", "3015001", "Heavy rain", "Hujan lebat")


def state(sid="BBR-a", level=Level.WARNING, p=0.62, win=True):
    return StreetState(sid, level, Level.WATCH, "high", p, ("rule_rain", "model"),
                       T0 + timedelta(minutes=30) if win else None, T0 + timedelta(minutes=90) if win else None,
                       (reason(),), T0)


def alert(sid="BBR-a", level=Level.WARNING, kind="alert", at=T0, win=True):
    return Alert(sid, level, kind, at, at + timedelta(minutes=30) if win else None,
                 at + timedelta(minutes=90) if win else None, (reason(),), ("rule_rain",))


def test_connect_creates_tables():
    eng = repo.connect("sqlite://")
    assert set(inspect(eng).get_table_names()) == set(schema.metadata.tables)
    assert {"street_state", "alerts", "answers", "subscriptions", "subscription_streets", "sensor_readings",
            "suggestions", "ops_notes", "admin_users", "stations", "readings", "streets"} <= set(schema.metadata.tables)


def test_postgres_types():
    for table in schema.metadata.sorted_tables:
        assert str(CreateTable(table).compile(dialect=postgresql.dialect()))


def test_states_round_trip(conn):
    s = state()
    repo.save_street_states(conn, [s, state("BBR-b", Level.NORMAL, None, win=False), state("KL-x")], "live")
    rows = {r["street_id"]: r for r in repo.get_street_states(conn, "BBR", "live")}
    assert set(rows) == {"BBR-a", "BBR-b"}
    r = rows["BBR-a"]
    assert r["level"] == "warning" and r["trigger_level"] == "watch" and r["confidence"] == "high"
    assert r["flood_probability"] == 0.62 and r["fired_by"] == ["rule_rain", "model"]
    assert r["window"] == {"start": "2024-11-12T09:30:00+08:00", "end": "2024-11-12T10:30:00+08:00"}
    assert r["data_time"] == "2024-11-12T09:00:00+08:00"
    assert r["reasons"] == [{"code": "rain_1h", "value": 45.5, "unit": "mm", "station": "3015001",
                             "text": {"en": "Heavy rain", "ms": "Hujan lebat"}}]
    assert rows["BBR-b"]["flood_probability"] is None and rows["BBR-b"]["window"] is None
    repo.save_street_states(conn, [state(level=Level.DANGER)], "live")   # replaces, no duplicate
    again = [r for r in repo.get_street_states(conn, "BBR", "live") if r["street_id"] == "BBR-a"]
    assert len(again) == 1 and again[0]["level"] == "danger"
    assert repo.get_street_states(conn, "BBR", "replay") == []           # modes are separate


def test_alert_ids_and_flags(conn, monkeypatch):
    monkeypatch.setattr(repo, "now_myt", lambda: T0 + timedelta(minutes=45))
    live = repo.insert_alerts(conn, [alert("BBR-a", Level.WATCH, at=T0 - timedelta(hours=3)),
                                     alert("BBR-a", Level.WARNING), alert("BBR-b", Level.WARNING, "all_clear", win=False)],
                              is_replay=False, is_backfill=False)
    rep = repo.insert_alerts(conn, [alert("BBR-a")], is_replay=True, is_backfill=False)
    bf = repo.insert_alerts(conn, [alert("BBR-a")], is_replay=False, is_backfill=True)
    ids = live + rep + bf
    assert len(ids) == len(set(ids)) == 5
    assert repo.insert_alerts(conn, [alert("BBR-a")], is_replay=False, is_backfill=False) == [live[1]]  # idempotent
    allrows = repo.list_alerts(conn)
    assert len(allrows) == 5
    assert [a["alert_id"] for a in allrows][0] in ids and allrows[-1]["issued_at"] == "2024-11-12T06:00:00+08:00"
    assert not any(a["is_replay"] for a in repo.list_alerts(conn, include_replay=False))
    assert len(repo.list_alerts(conn, include_replay=False)) == 4
    a = next(x for x in allrows if x["alert_id"] == rep[0])
    assert a == {"alert_id": rep[0], "street_id": "BBR-a", "horizon": "nowcast", "kind": "alert", "level": "warning",
                 "issued_at": "2024-11-12T09:00:00+08:00",
                 "window": {"start": "2024-11-12T09:30:00+08:00", "end": "2024-11-12T10:30:00+08:00"},
                 "outcome": "unverified", "is_replay": True, "push": True}
    assert {x["street_id"] for x in repo.list_alerts(conn, street_id="BBR-b")} == {"BBR-b"}
    assert len(repo.list_alerts(conn, since=T0)) == 4
    act = repo.list_alerts(conn, active=True, include_replay=False)
    assert [x["street_id"] for x in act] == ["BBR-a"] and act[0]["level"] == "warning"   # all-clear and old watch are not active
    monkeypatch.setattr(repo, "now_myt", lambda: T0 + timedelta(hours=5))
    assert repo.list_alerts(conn, active=True) == []                                       # window and cooldown over


def test_duplicate_answer(conn):
    base = {"device_id": "d1", "alert_id": "al1", "street_id": "BBR-a", "answer": "yes", "depth": "knee",
            "answered_at": T0, "source": "resident"}
    first = repo.insert_answer(conn, base)
    with pytest.raises(repo.DuplicateAnswer):
        repo.insert_answer(conn, base)
    repo.insert_answer(conn, {**base, "device_id": "d2"})
    r1 = repo.insert_answer(conn, {**base, "alert_id": None, "answer": "report"})
    r2 = repo.insert_answer(conn, {**base, "alert_id": None, "answer": "report"})
    assert len({first, r1, r2}) == 3
    assert len(repo.list_answers(conn)) == 4
    assert len(repo.list_answers(conn, alert_id="al1")) == 2
    row = repo.list_answers(conn, alert_id="al1", street_id="BBR-a")[0]
    assert row["review_status"] == "pending" and row["depth"] == "knee" and row["source"] == "resident"
    assert row["answered_at"] == "2024-11-12T09:00:00+08:00"
    repo.set_answer_review(conn, first, "spam")
    assert [a["answer_id"] for a in repo.list_answers(conn, review_status="spam")] == [first]


def test_subscriptions_and_delete_device(conn, tmp_path):
    sub = {"endpoint": "https://push/1", "keys": {"p256dh": "P", "auth": "A"}}
    repo.upsert_subscription(conn, "d1", sub, ["BBR-a", "BBR-b"], "ms")
    repo.upsert_subscription(conn, "d2", {**sub, "endpoint": "https://push/2"}, ["BBR-a"], "en")
    repo.upsert_subscription(conn, "d1", sub, ["BBR-b"], "en")   # replaces streets and language
    assert repo.list_subscribers(conn, "BBR-a") == [
        {"device_id": "d2", "endpoint": "https://push/2", "p256dh": "P", "auth": "A", "lang": "en"}]
    assert [s["device_id"] for s in repo.list_subscribers(conn, "BBR-b")] == ["d1"]
    photo = tmp_path / "p.jpg"
    photo.write_bytes(b"x")
    other = tmp_path / "q.jpg"
    other.write_bytes(b"x")
    ans = {"alert_id": "al1", "street_id": "BBR-a", "answer": "yes", "answered_at": T0, "source": "resident"}
    repo.insert_answer(conn, {**ans, "device_id": "d1", "photo_path": str(photo)})
    repo.insert_answer(conn, {**ans, "device_id": "d2", "photo_path": str(other)})
    repo.delete_device(conn, "d1")
    assert repo.list_subscribers(conn, "BBR-b") == []
    assert [s["device_id"] for s in repo.list_subscribers(conn, "BBR-a")] == ["d2"]
    assert [a["device_id"] for a in repo.list_answers(conn)] == ["d2"]
    assert not photo.exists() and other.exists()
    repo.delete_device(conn, "nobody")   # no error


def test_sensor_suggestions_notes(conn):
    repo.insert_sensor_reading(conn, "s1", T0, 12.5, True)
    assert conn.execute(schema.sensor_readings.select()).mappings().one()["simulated"] is True
    sug = {"id": "s_01", "street_id": "BBR-a", "rule": "SUG-1", "priority": "high", "text": "Review.",
           "evidence": {"flood_dates": ["2024-11-12"]}, "status": "open", "note": None,
           "period_from": T0.date(), "period_to": T0.date()}
    repo.upsert_suggestions(conn, [sug])
    repo.upsert_suggestions(conn, [{**sug, "text": "Review again."}])
    rows = conn.execute(schema.suggestions.select()).mappings().all()
    assert len(rows) == 1 and rows[0]["text"] == "Review again."
    repo.update_suggestion(conn, "s_01", "accepted", "ok")
    row = conn.execute(schema.suggestions.select()).mappings().one()
    assert row["status"] == "accepted" and row["note"] == "ok"
    n1 = repo.insert_note(conn, "BBR-a", "Drain blocked", "ops@x")
    n2 = repo.insert_note(conn, "BBR-a", "Cleared", "ops@x")
    assert n2 > n1


def test_db_init_script(tmp_path):
    import subprocess
    import sys
    db = tmp_path / "f.db"
    subprocess.run([sys.executable, "scripts/db_init.py", "--url", f"sqlite:///{db.as_posix()}"], check=True)
    names = {r[0] for r in sqlite3.connect(db).execute("select name from sqlite_master where type='table'")}
    assert set(schema.metadata.tables) <= names
