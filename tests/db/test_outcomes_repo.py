from datetime import datetime, timedelta

import pytest

from floodready.db import repo
from floodready.engine.types import Alert, Level, Reason

T0 = datetime(2024, 11, 12, 9, 0)


@pytest.fixture
def conn():
    eng = repo.connect("sqlite://")
    with eng.begin() as c:
        yield c


def make_alert(street="BBR-a", level=Level.WARNING, kind="alert", at=T0):
    return Alert(street, level, kind, at, at + timedelta(minutes=30), at + timedelta(minutes=90),
                 (Reason("rain_1h", 60.0, "mm", "1", "Heavy rain", "Hujan lebat"),), ("rule_rain",))


def answer(device, aid, kind="yes", minutes=10, **kw):
    return {"device_id": device, "alert_id": aid, "street_id": "BBR-a", "answer": kind,
            "answered_at": T0 + timedelta(minutes=minutes), **kw}


def test_unanswered_alert_is_unverified(conn):
    [aid] = repo.insert_alerts(conn, [make_alert()], is_replay=False, is_backfill=False)
    assert repo.list_alerts(conn)[0]["outcome"] == "unverified"
    assert aid


def test_two_yes_answers_confirm_and_three_no_do_not_confirm(conn):
    [a1, a2] = repo.insert_alerts(conn, [make_alert("BBR-a"), make_alert("BBR-b")], is_replay=False, is_backfill=False)
    repo.insert_answer(conn, answer("d1", a1))
    repo.insert_answer(conn, answer("d2", a1))
    for i in range(3):
        repo.insert_answer(conn, {**answer(f"n{i}", a2, "no"), "street_id": "BBR-b"})
    out = {a["alert_id"]: a["outcome"] for a in repo.list_alerts(conn)}
    assert out == {a1: "confirmed", a2: "not_confirmed"}


def test_answer_outside_three_hours_is_ignored(conn):
    [a1] = repo.insert_alerts(conn, [make_alert()], is_replay=False, is_backfill=False)
    repo.insert_answer(conn, answer("d1", a1, minutes=200))
    repo.insert_answer(conn, answer("d2", a1, minutes=210))
    assert repo.list_alerts(conn)[0]["outcome"] == "unverified"


@pytest.fixture
def sensors(monkeypatch):
    monkeypatch.setattr(repo, "sensor_devices", lambda: {"real-1": {"BBR-a"}, "sim-1": {"BBR-a"}})


def test_real_sensor_above_threshold_confirms_its_own_street_only(conn, sensors):
    [a, b] = repo.insert_alerts(conn, [make_alert("BBR-a"), make_alert("BBR-b")], is_replay=False, is_backfill=False)
    repo.insert_sensor_reading(conn, "real-1", T0 + timedelta(minutes=5), 2.0, False)
    assert {x["alert_id"]: x["outcome"] for x in repo.list_alerts(conn)} == {a: "unverified", b: "unverified"}
    repo.insert_sensor_reading(conn, "real-1", T0 + timedelta(minutes=20), 40.0, False)
    assert {x["alert_id"]: x["outcome"] for x in repo.list_alerts(conn)} == {a: "confirmed", b: "unverified"}


def test_unmapped_device_confirms_nothing(conn, sensors):
    repo.insert_alerts(conn, [make_alert("BBR-a")], is_replay=False, is_backfill=False)
    repo.insert_sensor_reading(conn, "other", T0 + timedelta(minutes=20), 40.0, False)
    assert repo.list_alerts(conn)[0]["outcome"] == "unverified"


def test_simulated_sensor_never_confirms_a_live_alert(conn, sensors):
    repo.insert_alerts(conn, [make_alert("BBR-a")], is_replay=False, is_backfill=False)
    repo.insert_sensor_reading(conn, "sim-1", T0 + timedelta(minutes=20), 40.0, True)
    assert repo.list_alerts(conn)[0]["outcome"] == "unverified"


def test_simulated_sensor_confirms_a_replay_alert_without_time_window(conn, sensors):
    [a, b] = repo.insert_alerts(conn, [make_alert("BBR-a"), make_alert("BBR-b")], is_replay=True, is_backfill=False)
    repo.insert_sensor_reading(conn, "sim-1", datetime(2026, 10, 18, 12, 0), 40.0, True)
    assert {x["alert_id"]: x["outcome"] for x in repo.list_alerts(conn)} == {a: "confirmed", b: "unverified"}
    assert repo.list_alerts(conn, count_simulated_sensor=False)[0]["outcome"] == "unverified"


def test_sensor_reading_before_the_alert_does_not_confirm(conn, sensors):
    repo.insert_alerts(conn, [make_alert("BBR-a")], is_replay=False, is_backfill=False)
    repo.insert_sensor_reading(conn, "real-1", T0 - timedelta(minutes=5), 40.0, False)
    assert repo.list_alerts(conn)[0]["outcome"] == "unverified"


def test_spam_answers_do_not_count(conn):
    [a1] = repo.insert_alerts(conn, [make_alert()], is_replay=False, is_backfill=False)
    repo.insert_answer(conn, answer("d1", a1))
    repo.insert_answer(conn, answer("d2", a1, review_status="spam"))
    assert repo.list_alerts(conn)[0]["outcome"] == "unverified"


def test_replay_alert_is_scored_on_demo_answers_without_time_window(conn):
    [aid] = repo.insert_alerts(conn, [make_alert()], is_replay=True, is_backfill=False)
    now = datetime(2026, 10, 18, 12, 0)     # demo answers arrive in wall-clock time, years after the 2024 replay alert
    for d in ("a", "b"):
        repo.insert_answer(conn, {"device_id": d, "alert_id": aid, "street_id": "BBR-a", "answer": "yes",
                                  "answered_at": now, "source": "demo"})
    assert repo.list_alerts(conn)[0]["outcome"] == "confirmed"


def test_outcomes_for_runner_style_alert_dicts(conn):
    [a1] = repo.insert_alerts(conn, [make_alert()], is_replay=False, is_backfill=False)
    repo.insert_answer(conn, answer("d1", a1))
    repo.insert_answer(conn, answer("d2", a1))
    items = [{"alert_id": a1, "street_id": "BBR-a", "kind": "alert", "issued_at": "2024-11-12T09:00:00+08:00"},
             {"alert_id": "x", "street_id": "BBR-a", "kind": "all_clear", "issued_at": "2024-11-12T09:00:00+08:00"}]
    assert repo.outcomes_for(conn, items) == {a1: "confirmed", "x": "unverified"}
