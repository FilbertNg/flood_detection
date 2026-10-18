from floodready.db import repo
from tests.db.test_repo import alert, state


def test_clear_replay_removes_replay_alerts_and_states_only():
    eng = repo.connect("sqlite://")
    with eng.begin() as c:
        repo.insert_alerts(c, [alert("BBR-a")], is_replay=False, is_backfill=False)
        repo.insert_alerts(c, [alert("BBR-b")], is_replay=True, is_backfill=False)
        repo.insert_alerts(c, [alert("BBR-c")], is_replay=False, is_backfill=True)
        repo.save_street_states(c, [state("BBR-a")], "live")
        repo.save_street_states(c, [state("BBR-b")], "replay")
        repo.clear_replay(c)
        ids = {a["street_id"] for a in repo.list_alerts(c, include_backfill=True)}
        assert ids == {"BBR-a", "BBR-c"}
        assert repo.get_street_states(c, "BBR", "replay") == []
        assert len(repo.get_street_states(c, "BBR", "live")) == 1


def test_a_cleared_replay_alert_is_new_again():
    eng = repo.connect("sqlite://")
    with eng.begin() as c:
        assert len(repo.insert_alerts(c, [alert()], is_replay=True, is_backfill=False)) == 1
        assert repo.insert_alerts(c, [alert()], is_replay=True, is_backfill=False) == []
        repo.clear_replay(c)
        assert len(repo.insert_alerts(c, [alert()], is_replay=True, is_backfill=False)) == 1


def test_clear_replay_deletes_demo_answers_and_simulated_readings_but_keeps_real_ones(tmp_path):
    from datetime import datetime
    from sqlalchemy import select
    from floodready.db import schema
    eng = repo.connect("sqlite://")
    photo = tmp_path / "demo.jpg"
    photo.write_bytes(b"x")
    with eng.begin() as c:
        [rid] = repo.insert_alerts(c, [alert("BBR-b")], is_replay=True, is_backfill=False)
        [lid] = repo.insert_alerts(c, [alert("BBR-a")], is_replay=False, is_backfill=False)
        base = {"street_id": "BBR-b", "answer": "yes"}
        repo.insert_answer(c, {**base, "device_id": "d1", "alert_id": rid, "source": "demo", "photo_path": "demo.jpg"})
        repo.insert_answer(c, {**base, "device_id": "d2", "alert_id": None, "source": "demo"})
        repo.insert_answer(c, {**base, "device_id": "d3", "alert_id": lid, "street_id": "BBR-a"})
        repo.insert_sensor_reading(c, "sim-1", datetime(2026, 10, 18, 9, 0), 40, True)
        repo.insert_sensor_reading(c, "real-1", datetime(2026, 10, 18, 9, 0), 40, False)
        files = repo.clear_replay(c, uploads=tmp_path)
        assert [a["device_id"] for a in repo.list_answers(c)] == ["d3"]
        assert [r.device_id for r in c.execute(select(schema.sensor_readings))] == ["real-1"]
    assert files == [photo.resolve()] and photo.exists()          # removal is the caller's job, after the commit
    repo.remove_files(files)
    assert not photo.exists()


def test_delete_subscription_keeps_answers():
    eng = repo.connect("sqlite://")
    with eng.begin() as c:
        repo.upsert_subscription(c, "d1", {"endpoint": "https://x", "keys": {"p256dh": "p", "auth": "a"}}, ["BBR-a"], "en")
        repo.insert_answer(c, {"device_id": "d1", "alert_id": None, "street_id": "BBR-a", "answer": "report"})
        repo.delete_subscription(c, "d1")
        assert repo.list_subscribers(c, "BBR-a") == []
        assert len(repo.list_answers(c)) == 1
