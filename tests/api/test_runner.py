from datetime import date, datetime

from floodready.engine.types import Level

T = lambda hhmm: datetime(2024, 11, 12, int(hhmm[:2]), int(hhmm[3:]))  # noqa: E731


def test_replay_runs_to_the_end_and_logs_alerts(runner):
    runner.start_replay(date(2024, 11, 12), speed=None, start="06:00", end="14:00")
    snap = runner.snapshot()
    assert snap.mode == "replay" and snap.step.time == T("14:00")
    first = [a for a in reversed(snap.alerts) if a["street_id"] == "BBR-prone-street"][:3]   # log is newest-first
    assert [(a["kind"], a["level"], a["issued_at"]) for a in first] == [
        ("alert", "watch", "2024-11-12T08:45:00+08:00"), ("alert", "warning", "2024-11-12T09:00:00+08:00"), ("alert", "danger", "2024-11-12T10:00:00+08:00")]
    assert all(a["is_replay"] for a in snap.alerts)


def test_replay_can_stop_at_a_chosen_time(runner):
    runner.start_replay(date(2024, 11, 12), speed=None, start="06:00", end="14:00", stop_at="09:00")
    snap = runner.snapshot()
    assert snap.step.time == T("09:00") and snap.step.trigger.level is Level.WARNING


def test_stopping_replay_returns_to_live(runner):
    runner.start_replay(date(2024, 11, 12), speed=None, start="06:00", end="08:00")
    runner.stop_replay()
    assert runner.snapshot().mode == "live"


def test_a_live_refresh_that_finishes_after_a_replay_started_does_not_overwrite_it(context):
    from floodready.api.runner import Runner
    import pandas as pd
    runner = Runner(context)

    def live_readings_while_a_replay_starts(since):
        # The live refresh is slow (archive load); a replay is started meanwhile.
        runner.start_replay(date(2024, 11, 12), speed=None, start="06:00", end="14:00", stop_at="09:00")
        return pd.DataFrame(columns=["graph_id", "kind", "time_local", "rain_15min_mm", "wl_m"])

    context.load_live_readings = live_readings_while_a_replay_starts
    runner.refresh_live(datetime(2024, 11, 13, 12, 0))
    snap = runner.snapshot()
    assert snap.mode == "replay" and snap.step.time == T("09:00")


def test_alerts_carry_a_push_flag_from_config(runner):
    runner.start_replay(date(2024, 11, 12), speed=None, start="06:00", end="14:00")
    alerts = runner.snapshot().alerts
    assert {a["level"] for a in alerts} >= {"watch", "warning"}
    assert all(a["push"] == (a["level"] in ("watch", "warning", "danger")) for a in alerts if a["kind"] == "alert")
    assert not any(a["push"] for a in alerts if a["kind"] != "alert")       # all-clears are never pushed
