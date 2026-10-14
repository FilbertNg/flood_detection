from datetime import date, datetime

from floodready.engine.types import Level

T = lambda hhmm: datetime(2024, 11, 12, int(hhmm[:2]), int(hhmm[3:]))  # noqa: E731


def test_replay_runs_to_the_end_and_logs_alerts(runner):
    runner.start_replay(date(2024, 11, 12), speed=None, start="06:00", end="14:00")
    snap = runner.snapshot()
    assert snap.mode == "replay" and snap.step.time == T("14:00")
    first = [a for a in reversed(snap.alerts) if a["street_id"] == "BBR-prone-street"][:2]   # log is newest-first
    assert [(a["kind"], a["level"], a["issued_at"]) for a in first] == [
        ("alert", "warning", "2024-11-12T09:00:00+08:00"), ("alert", "danger", "2024-11-12T10:00:00+08:00")]
    assert all(a["is_replay"] for a in snap.alerts)


def test_replay_can_stop_at_a_chosen_time(runner):
    runner.start_replay(date(2024, 11, 12), speed=None, start="06:00", end="14:00", stop_at="09:00")
    snap = runner.snapshot()
    assert snap.step.time == T("09:00") and snap.step.trigger.level is Level.WARNING


def test_stopping_replay_returns_to_live(runner):
    runner.start_replay(date(2024, 11, 12), speed=None, start="06:00", end="08:00")
    runner.stop_replay()
    assert runner.snapshot().mode == "live"
