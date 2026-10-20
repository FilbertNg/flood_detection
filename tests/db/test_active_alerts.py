import dataclasses
from datetime import timedelta

from floodready.db import repo
from floodready.engine.types import Level
from tests.db.test_repo import T0, alert, state


def test_alert_is_active_only_while_the_street_is_above_normal():
    eng = repo.connect("sqlite://")
    with eng.begin() as c:
        repo.insert_alerts(c, [alert("BBR-a"), alert("BBR-b"), alert("BBR-c")], is_replay=False, is_backfill=False)
        late = dataclasses.replace(state("BBR-b", Level.NORMAL), data_time=T0 + timedelta(hours=2))   # past the all-clear hold
        repo.save_street_states(c, [state("BBR-a", Level.WARNING), late], "live")
        active = {a["street_id"] for a in repo.list_alerts(c, active=True)}
    assert active == {"BBR-a", "BBR-c"}      # b: missed all-clear, normal past the hold; c: no state row yet, kept


def test_replay_only_returns_replay_rows():
    eng = repo.connect("sqlite://")
    with eng.begin() as c:
        repo.insert_alerts(c, [alert("BBR-a")], is_replay=False, is_backfill=False)
        repo.insert_alerts(c, [alert("BBR-a")], is_replay=True, is_backfill=False)
        assert [a["is_replay"] for a in repo.list_alerts(c, replay_only=True)] == [True]
