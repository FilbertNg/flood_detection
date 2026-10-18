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


def test_delete_subscription_keeps_answers():
    eng = repo.connect("sqlite://")
    with eng.begin() as c:
        repo.upsert_subscription(c, "d1", {"endpoint": "https://x", "keys": {"p256dh": "p", "auth": "a"}}, ["BBR-a"], "en")
        repo.insert_answer(c, {"device_id": "d1", "alert_id": None, "street_id": "BBR-a", "answer": "report"})
        repo.delete_subscription(c, "d1")
        assert repo.list_subscribers(c, "BBR-a") == []
        assert len(repo.list_answers(c)) == 1
