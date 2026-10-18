from floodready.db import repo
from floodready.engine.types import Level
from tests.db.test_repo import alert, state


def test_alert_is_active_only_while_the_street_is_above_normal():
    eng = repo.connect("sqlite://")
    with eng.begin() as c:
        repo.insert_alerts(c, [alert("BBR-a"), alert("BBR-b"), alert("BBR-c")], is_replay=False, is_backfill=False)
        repo.save_street_states(c, [state("BBR-a", Level.WARNING), state("BBR-b", Level.NORMAL)], "live")
        active = {a["street_id"] for a in repo.list_alerts(c, active=True)}
    assert active == {"BBR-a", "BBR-c"}      # b: missed all-clear, state normal; c: no state row yet, kept


def test_replay_only_returns_replay_rows():
    eng = repo.connect("sqlite://")
    with eng.begin() as c:
        repo.insert_alerts(c, [alert("BBR-a")], is_replay=False, is_backfill=False)
        repo.insert_alerts(c, [alert("BBR-a")], is_replay=True, is_backfill=False)
        assert [a["is_replay"] for a in repo.list_alerts(c, replay_only=True)] == [True]
