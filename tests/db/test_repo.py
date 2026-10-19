import sqlite3
from datetime import datetime, timedelta

import pytest
from sqlalchemy import inspect
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
    repo.save_street_states(conn, [s, state("BBR-b", Level.NORMAL, None, win=False), state("KL-x"), state("BBRX-y")], "live")
    rows = {r["street_id"]: r for r in repo.get_street_states(conn, "BBR", "live")}
    assert set(rows) == {"BBR-a", "BBR-b"}                      # exact township prefix, no LIKE wildcards
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


def test_alert_ids_and_flags(conn):
    live = repo.insert_alerts(conn, [alert("BBR-a", Level.WATCH, at=T0 - timedelta(hours=3)),
                                     alert("BBR-a", Level.WARNING), alert("BBR-b", Level.WARNING, "all_clear", win=False)],
                              is_replay=False, is_backfill=False)
    assert live[1] == "BBR-a@20241112T0900-alert"                        # live nowcast id = the runner's format
    rep = repo.insert_alerts(conn, [alert("BBR-a")], is_replay=True, is_backfill=False)
    bf = repo.insert_alerts(conn, [alert("BBR-a")], is_replay=False, is_backfill=True)
    ids = live + rep + bf
    assert len(ids) == len(set(ids)) == 5
    assert repo.insert_alerts(conn, [alert("BBR-a")], is_replay=False, is_backfill=False) == []   # only NEW ids returned
    outlook = repo.insert_alerts(conn, [alert("BBR-a")], is_replay=False, is_backfill=False, horizon="outlook")
    assert len(outlook) == 1 and outlook[0] not in ids                   # same street/tick/kind does not collide
    allrows = repo.list_alerts(conn)
    assert len(allrows) == 5 and not any(x["alert_id"] in bf for x in allrows)   # backfill never leaks by default
    assert allrows[-1]["issued_at"] == "2024-11-12T06:00:00+08:00"
    assert {x["alert_id"] for x in repo.list_alerts(conn, include_backfill=True)} == set(ids) | set(outlook)
    assert not any(a["is_replay"] for a in repo.list_alerts(conn, include_replay=False))
    assert len(repo.list_alerts(conn, include_replay=False)) == 4
    a = next(x for x in allrows if x["alert_id"] == rep[0])
    assert a == {"alert_id": rep[0], "street_id": "BBR-a", "horizon": "nowcast", "kind": "alert", "level": "warning",
                 "issued_at": "2024-11-12T09:00:00+08:00",
                 "window": {"start": "2024-11-12T09:30:00+08:00", "end": "2024-11-12T10:30:00+08:00"},
                 "outcome": "unverified", "is_replay": True, "push": True}
    assert next(x for x in allrows if x["horizon"] == "outlook")["alert_id"] == outlook[0]
    assert {x["street_id"] for x in repo.list_alerts(conn, street_id="BBR-b")} == {"BBR-b"}
    assert len(repo.list_alerts(conn, since=T0)) == 4


def test_active_follows_engine_not_wall_clock(conn):
    # steady Warning: one alert at 09:00, nothing later; still active 2 h (and years) after, until the all-clear
    repo.insert_alerts(conn, [alert("BBR-a", Level.WARNING)], is_replay=False, is_backfill=False)
    repo.insert_alerts(conn, [alert("BBR-a", Level.WATCH, at=T0 - timedelta(hours=2))], is_replay=False, is_backfill=False)
    assert [x["level"] for x in repo.list_alerts(conn, active=True)] == ["warning"]
    repo.insert_alerts(conn, [alert("BBR-a", Level.NORMAL, "all_clear", at=T0 + timedelta(hours=3), win=False)],
                       is_replay=False, is_backfill=False)
    assert repo.list_alerts(conn, active=True) == []
    # modes do not mix: a replay Danger is active in replay mode, and live all-clear does not cancel it
    repo.insert_alerts(conn, [alert("BBR-a", Level.DANGER)], is_replay=True, is_backfill=False)
    act = repo.list_alerts(conn, active=True)
    assert [(x["level"], x["is_replay"]) for x in act] == [("danger", True)]
    assert repo.list_alerts(conn, active=True, include_replay=False) == []
    # backfill is never active in the default view
    repo.insert_alerts(conn, [alert("BBR-b", Level.DANGER)], is_replay=False, is_backfill=True)
    assert [x["street_id"] for x in repo.list_alerts(conn, active=True)] == ["BBR-a"]


def test_replace_backfill(conn):
    repo.insert_alerts(conn, [alert("BBR-a", at=T0), alert("BBR-a", at=T0 + timedelta(days=40))],
                       is_replay=False, is_backfill=True)
    repo.insert_alerts(conn, [alert("BBR-a")], is_replay=False, is_backfill=False)
    n = repo.replace_backfill(conn, "BBR", datetime(2024, 11, 1), datetime(2024, 12, 1))
    assert n == 1
    ids = [x["issued_at"] for x in repo.list_alerts(conn, include_backfill=True)]
    assert len(ids) == 2 and "2024-12-22T09:00:00+08:00" in ids
    new = repo.insert_alerts(conn, [alert("BBR-a", at=T0)], is_replay=False, is_backfill=True)   # re-run rewrites
    assert len(new) == 1


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
    assert len(repo.list_answers(conn)) == 4                              # connection still usable after the duplicate
    assert len(repo.list_answers(conn, alert_id="al1")) == 2
    row = repo.list_answers(conn, alert_id="al1", street_id="BBR-a")[0]
    assert row["review_status"] == "pending" and row["depth"] == "knee" and row["source"] == "resident"
    assert row["answered_at"] == "2024-11-12T09:00:00+08:00"
    repo.set_answer_review(conn, first, "spam")
    assert [a["answer_id"] for a in repo.list_answers(conn, review_status="spam")] == [first]


def test_other_integrity_errors_are_not_duplicates(conn):
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        repo.insert_answer(conn, {"device_id": "d1", "alert_id": "a", "street_id": "BBR-a", "answer": None,
                                  "answered_at": T0})
    assert repo.list_answers(conn) == []                                  # savepoint rolled back, connection fine


def test_subscriptions_and_delete_device(conn, tmp_path):
    sub = {"endpoint": "https://push/1", "keys": {"p256dh": "P", "auth": "A"}}
    repo.upsert_subscription(conn, "d1", sub, ["BBR-a", "BBR-b"], "ms")
    created = conn.execute(schema.subscriptions.select()).mappings().first()["created_at"]
    repo.upsert_subscription(conn, "d2", {**sub, "endpoint": "https://push/2"}, ["BBR-a"], "en")
    repo.upsert_subscription(conn, "d1", sub, ["BBR-b"], "en")   # replaces streets and language, keeps created_at
    d1 = conn.execute(schema.subscriptions.select().where(schema.subscriptions.c.device_id == "d1")).mappings().one()
    assert d1["created_at"] == created and d1["lang"] == "en"
    assert repo.list_subscribers(conn, "BBR-a") == [
        {"device_id": "d2", "endpoint": "https://push/2", "p256dh": "P", "auth": "A", "lang": "en"}]
    assert [s["device_id"] for s in repo.list_subscribers(conn, "BBR-b")] == ["d1"]
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    photo, other = uploads / "p.jpg", uploads / "q.jpg"
    outside = tmp_path / "secret.txt"
    for f in (photo, other, outside):
        f.write_bytes(b"x")
    ans = {"alert_id": "al1", "street_id": "BBR-a", "answer": "yes", "answered_at": T0, "source": "resident"}
    repo.insert_answer(conn, {**ans, "device_id": "d1", "photo_path": str(photo)})
    repo.insert_answer(conn, {**ans, "alert_id": "al2", "device_id": "d1", "photo_path": str(outside)})
    repo.insert_answer(conn, {**ans, "alert_id": "al3", "device_id": "d1", "photo_path": str(uploads / ".." / "secret.txt")})
    repo.insert_answer(conn, {**ans, "device_id": "d2", "photo_path": str(other)})
    files = repo.delete_device(conn, "d1", uploads=uploads)
    assert files == [photo.resolve()]                                     # only files inside uploads, and not yet deleted
    assert photo.exists() and outside.exists()
    repo.remove_files(files)                                              # caller does this after commit
    assert not photo.exists() and other.exists() and outside.exists()
    assert repo.list_subscribers(conn, "BBR-b") == []
    assert [s["device_id"] for s in repo.list_subscribers(conn, "BBR-a")] == ["d2"]
    assert [a["device_id"] for a in repo.list_answers(conn)] == ["d2"]
    assert repo.delete_device(conn, "nobody", uploads=uploads) == []


def test_sensor_suggestions_notes(conn):
    repo.insert_sensor_reading(conn, "s1", T0, 12.5, True)
    assert conn.execute(schema.sensor_readings.select()).mappings().one()["simulated"] is True
    sug = {"id": "s_01", "street_id": "BBR-a", "rule": "SUG-1", "priority": "high", "text": "Review.",
           "evidence": {"flood_dates": ["2024-11-12"]}, "period_from": T0.date(), "period_to": T0.date()}
    repo.upsert_suggestions(conn, [sug])
    row = conn.execute(schema.suggestions.select()).mappings().one()
    assert row["status"] == "open"
    created = row["created_at"]
    repo.update_suggestion(conn, "s_01", "accepted", "ok")
    repo.upsert_suggestions(conn, [{**sug, "text": "Review again."}])     # regenerate: keeps admin decision
    row = conn.execute(schema.suggestions.select()).mappings().one()
    assert row["text"] == "Review again." and row["status"] == "accepted" and row["note"] == "ok"
    assert row["created_at"] == created
    n1 = repo.insert_note(conn, "BBR-a", "Drain blocked", "ops@x")
    n2 = repo.insert_note(conn, "BBR-a", "Cleared", "ops@x")
    assert n2 > n1


def test_push_levels_from_config():
    assert repo.push_levels() == ("watch", "warning", "danger")


def test_postgres_url_normalised(monkeypatch):
    seen = {}
    monkeypatch.setattr(repo, "create_engine", lambda url, **kw: seen.setdefault("url", url) and None)
    monkeypatch.setattr(repo.t.metadata, "create_all", lambda e: None)
    repo.connect("postgres://u:p@h/db")
    assert seen["url"] == "postgresql+psycopg://u:p@h/db"
    seen.clear()
    repo.connect("postgresql://u:p@h/db")
    assert seen["url"] == "postgresql+psycopg://u:p@h/db"


def test_db_init_script(tmp_path):
    import subprocess
    import sys
    db = tmp_path / "f.db"
    subprocess.run([sys.executable, "scripts/db_init.py", "--url", f"sqlite:///{db.as_posix()}"], check=True)
    names = {r[0] for r in sqlite3.connect(db).execute("select name from sqlite_master where type='table'")}
    assert set(schema.metadata.tables) <= names


def test_active_groups_by_horizon(conn):
    # a nowcast Warning and an outlook Watch on one street are both active; neither hides the other
    repo.insert_alerts(conn, [alert("BBR-a", Level.WARNING)], is_replay=False, is_backfill=False)
    repo.insert_alerts(conn, [alert("BBR-a", Level.WATCH, at=T0 + timedelta(hours=1), win=False)],
                       is_replay=False, is_backfill=False, horizon="outlook")
    act = repo.list_alerts(conn, active=True)
    assert sorted((x["horizon"], x["level"]) for x in act) == [("nowcast", "warning"), ("outlook", "watch")]
    assert any(x["alert_id"].endswith("~outlook") for x in act)
    # a nowcast all-clear (newer than the outlook row) clears only the nowcast
    repo.insert_alerts(conn, [alert("BBR-a", Level.NORMAL, "all_clear", at=T0 + timedelta(hours=2), win=False)],
                       is_replay=False, is_backfill=False)
    assert [(x["horizon"], x["level"]) for x in repo.list_alerts(conn, active=True)] == [("outlook", "watch")]
    # and an outlook all-clear clears only the outlook
    repo.insert_alerts(conn, [alert("BBR-a", Level.WARNING, at=T0 + timedelta(hours=3))], is_replay=False, is_backfill=False)
    repo.insert_alerts(conn, [alert("BBR-a", Level.NORMAL, "all_clear", at=T0 + timedelta(hours=4), win=False)],
                       is_replay=False, is_backfill=False, horizon="outlook")
    assert [(x["horizon"], x["level"]) for x in repo.list_alerts(conn, active=True)] == [("nowcast", "warning")]


def _outlook(sid="BBR-a", at=T0, kind="alert", rs=None, end_h=3):
    a = Alert(sid, Level.WATCH if kind == "alert" else Level.NORMAL, kind, at, at, at + timedelta(hours=end_h),
              tuple(rs if rs is not None else [Reason("met_warning", 0.0, "h", None, "MET", "MET")]), ("outlook",))
    return a


def test_outlook_expires_by_window_end_and_push_follows_reasons(conn):
    repo.insert_alerts(conn, [_outlook("BBR-a"), _outlook("BBR-b", rs=[Reason("forecast_rain", 50.0, "mm", None, "x", "x")])],
                       is_replay=False, is_backfill=False, horizon="outlook")
    act = {x["street_id"]: x for x in repo.list_alerts(conn, active=True, now=T0 + timedelta(hours=1))}
    assert set(act) == {"BBR-a", "BBR-b"}
    assert act["BBR-a"]["push"] is False and act["BBR-b"]["push"] is True      # in-force MET warning: stored, not pushed
    assert repo.list_alerts(conn, active=True, now=T0 + timedelta(hours=4)) == []      # window_end passed
    assert len(repo.list_alerts(conn)) == 2                                            # history keeps them


def test_latest_outlook_reseeds_the_runner(conn):
    assert repo.latest_outlook(conn, "BBR") == (None, [])
    repo.insert_alerts(conn, [_outlook("BBR-a"), _outlook("BBR-b")], is_replay=False, is_backfill=False, horizon="outlook")
    last, streets = repo.latest_outlook(conn, "BBR")
    assert last.kind == "alert" and last.issued_at == T0 and sorted(streets) == ["BBR-a", "BBR-b"]
    assert last.reasons[0].code == "met_warning" and last.window_end == T0 + timedelta(hours=3)
    repo.insert_alerts(conn, [_outlook("BBR-a", T0 + timedelta(hours=1), "all_clear", rs=[])],
                       is_replay=False, is_backfill=False, horizon="outlook")
    last, streets = repo.latest_outlook(conn, "BBR")
    assert last.kind == "all_clear" and streets == []


# ---------- a held all-clear keeps the alert active (alerts.clear_after_min = 60) ----------

def _normal_at(conn, minutes, level=Level.NORMAL):
    import dataclasses
    repo.save_street_states(conn, [dataclasses.replace(state("BBR-a", level), data_time=T0 + timedelta(minutes=minutes))], "live")


def test_held_alert_is_active_during_the_hold_and_drops_out_after_it_without_an_all_clear(conn):
    repo.insert_alerts(conn, [alert("BBR-a", Level.WARNING)], is_replay=False, is_backfill=False)
    _normal_at(conn, 15)
    assert [x["level"] for x in repo.list_alerts(conn, active=True)] == ["warning"]       # held: still active
    _normal_at(conn, 59)
    assert len(repo.list_alerts(conn, active=True)) == 1
    _normal_at(conn, 75)                                                                  # all-clear never came
    assert repo.list_alerts(conn, active=True) == []


def test_danger_normal_danger_inside_the_hold_stays_active_throughout(conn):
    repo.insert_alerts(conn, [alert("BBR-a", Level.DANGER)], is_replay=False, is_backfill=False)
    _normal_at(conn, 15)
    assert len(repo.list_alerts(conn, active=True)) == 1
    _normal_at(conn, 30, Level.DANGER)
    assert [(x["level"], x["push"]) for x in repo.list_alerts(conn, active=True)] == [("danger", True)]
    assert len(repo.list_alerts(conn)) == 1                      # no second alert row, so no second push


def test_held_alert_follows_its_own_mode(conn):
    repo.insert_alerts(conn, [alert("BBR-a", Level.WARNING)], is_replay=True, is_backfill=False)
    _normal_at(conn, 15)                                          # a live Normal state does not affect a replay alert
    assert len(repo.list_alerts(conn, active=True)) == 1
