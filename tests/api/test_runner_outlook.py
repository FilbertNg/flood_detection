"""Outlook (E8) in the live runner: per street at Watch only where the nowcast is Normal; never in replay."""
from datetime import date, datetime
from types import SimpleNamespace

import pandas as pd
from fastapi.testclient import TestClient

from floodready.api.main import create_app
from floodready.engine.types import Level

NOW = datetime(2024, 11, 12, 10, 0)
WARNING = {"title_en": "Thunderstorms Warning", "title_ms": "Amaran Ribut Petir",
           "valid_from": datetime(2024, 11, 12, 8, 0), "valid_to": datetime(2024, 11, 12, 14, 0),
           "areas": {"Selangor": set()}}
NO_FORECAST = pd.DataFrame(columns=["time_local", "precip_mm"])
# the nowcast of the moment: the prone street is elevated, the safe street is Normal
STATES = [SimpleNamespace(street_id="BBR-prone-street", level=Level.WARNING),
          SimpleNamespace(street_id="BBR-safe-street", level=Level.NORMAL)]


def step(runner, warnings, now=NOW):
    runner.ctx.outlook_inputs = lambda at: (warnings, NO_FORECAST)
    runner._refresh_outlook(now, STATES, runner._generation)
    return runner.alerts()


def outlook_rows(alerts):
    return [a for a in alerts if a["horizon"] == "outlook"]


def test_outlook_only_on_streets_whose_nowcast_is_normal(runner):
    rows = outlook_rows(step(runner, [WARNING]))
    assert [(a["street_id"], a["kind"], a["level"]) for a in rows] == [("BBR-safe-street", "alert", "watch")]
    a = rows[0]
    assert a["alert_id"] == "BBR-safe-street@20241112T1000-alert~outlook" and a["push"] is False and a["is_replay"] is False
    assert a["window"] == {"start": "2024-11-12T10:00:00+08:00", "end": "2024-11-12T14:00:00+08:00"}


def test_outlook_is_not_repeated_then_clears_once(runner):
    step(runner, [WARNING])
    assert len(outlook_rows(step(runner, [WARNING], datetime(2024, 11, 12, 10, 15)))) == 1
    rows = outlook_rows(step(runner, [], datetime(2024, 11, 12, 10, 30)))
    assert [(a["kind"], a["street_id"], a["push"]) for a in rows[:1]] == [("all_clear", "BBR-safe-street", False)]
    assert len(outlook_rows(step(runner, [], datetime(2024, 11, 12, 10, 45)))) == 2


def test_no_inputs_no_outlook(runner):
    runner.refresh_live(NOW)
    assert outlook_rows(runner.alerts()) == []


def test_a_failing_outlook_does_not_break_the_nowcast(runner):
    def boom(at):
        raise RuntimeError("no forecast file")
    runner.ctx.outlook_inputs = boom
    runner.refresh_live(NOW)
    assert runner.snapshot().step is not None and outlook_rows(runner.alerts()) == []


def test_replay_never_issues_an_outlook(runner):
    runner.ctx.outlook_inputs = lambda at: ([WARNING], NO_FORECAST)
    runner.start_replay(date(2024, 11, 12), speed=None, start="06:00", end="14:00")
    assert outlook_rows(runner.alerts()) == []
    runner.refresh_live(NOW)                                  # ignored while replaying
    assert outlook_rows(runner.alerts()) == []


def test_active_alert_by_horizon_in_api(runner, monkeypatch):
    monkeypatch.setattr('floodready.db.repo.now_myt', lambda: NOW)
    runner.refresh_live(NOW)                                  # real nowcast alerts exist
    client = TestClient(create_app(runner, start_live_loop=False))
    step(runner, [WARNING])
    active = client.get("/api/v1/alerts", params={"active": "true"}).json()
    assert ("BBR-safe-street", "outlook") in {(a["street_id"], a["horizon"]) for a in active}
    assert any(a["horizon"] == "nowcast" for a in active)     # the outlook does not hide the nowcast alerts
    step(runner, [], datetime(2024, 11, 12, 10, 30))          # outlook all-clear
    active = client.get("/api/v1/alerts", params={"active": "true"}).json()
    assert not outlook_rows(active) and any(a["horizon"] == "nowcast" for a in active)


def test_in_force_warning_is_stored_but_not_pushed_and_a_distant_one_is(runner):
    rows = outlook_rows(step(runner, [WARNING]))                        # in force since 08:00
    assert rows[0]["push"] is False
    later = dict(WARNING, valid_from=datetime(2024, 11, 12, 17, 0), valid_to=datetime(2024, 11, 12, 20, 0))
    runner._outlook_last, runner._outlook_streets = None, []
    rows = outlook_rows(step(runner, [later], datetime(2024, 11, 12, 11, 0)))
    assert [(a["push"], a["window"]["start"]) for a in rows if a["issued_at"].startswith("2024-11-12T11")] == \
        [(True, "2024-11-12T17:00:00+08:00")]


def test_push_text_mentions_both_triggers(runner):
    sent = []
    runner.push.enqueue = lambda alerts, names: sent.extend(alerts)
    fc = pd.DataFrame({"time_local": [datetime(2024, 11, 12, 18)], "precip_mm": [50.0]})
    runner.ctx.outlook_inputs = lambda at: ([WARNING], fc)
    runner._refresh_outlook(NOW, STATES, runner._generation)
    text = sent[0]["reason_text"]["en"]
    assert "Thunderstorms Warning" in text and "50 mm" in text


def test_restart_mid_outlook_keeps_state(runner, context):
    from floodready.api.runner import Runner
    step(runner, [WARNING])
    again = Runner(context, db=runner.db)                               # restart: new process, same database
    assert again._outlook_last is not None and again._outlook_last.kind == "alert"
    again.ctx.outlook_inputs = lambda at: ([WARNING], NO_FORECAST)
    again._refresh_outlook(datetime(2024, 11, 12, 10, 15), STATES, again._generation)
    assert len(outlook_rows(again.alerts())) == 1                       # no duplicate alert
    again.ctx.outlook_inputs = lambda at: ([], NO_FORECAST)
    again._refresh_outlook(datetime(2024, 11, 12, 10, 30), STATES, again._generation)
    assert [a["kind"] for a in outlook_rows(again.alerts())][0] == "all_clear"
