from datetime import datetime, timedelta

import pytest

from floodready.engine import alerts
from floodready.engine.types import Level, StreetState

T = lambda hhmm: datetime(2024, 11, 12, int(hhmm[:2]), int(hhmm[3:]))  # noqa: E731


def state(level, when, street="BBR-a"):
    return StreetState(street_id=street, level=level, trigger_level=level, confidence="high", flood_probability=None,
                       fired_by=("rule_rain",), window_start=None, window_end=None, reasons=(), data_time=T(when))


class Engine:
    """Feeds states in time order and keeps the alert memory, like replay does."""

    def __init__(self, cfg):
        self.cfg, self.prev, self.last = cfg, {}, {}

    def step(self, level, when):
        new = [state(level, when)]
        issued = alerts.issue(self.prev, new, self.last, self.cfg)
        self.prev = {s.street_id: s for s in new}
        for a in issued:
            self.last[a.street_id] = a
        return issued


def test_warning_issues_an_alert(rules_cfg):
    issued = Engine(rules_cfg).step(Level.WARNING, "09:00")
    assert [(a.kind, a.level) for a in issued] == [("alert", Level.WARNING)]
    assert issued[0].issued_at == T("09:00")


def test_same_level_within_cooldown_is_not_repeated(rules_cfg):
    engine = Engine(rules_cfg)
    engine.step(Level.WARNING, "09:00")
    assert engine.step(Level.WARNING, "09:15") == []


def test_flapping_back_to_warning_within_cooldown_is_not_repeated(rules_cfg):
    engine = Engine(rules_cfg)
    engine.step(Level.WARNING, "09:00")
    engine.step(Level.WATCH, "09:15")
    assert engine.step(Level.WARNING, "09:30") == []


def test_rising_level_alerts_even_within_cooldown(rules_cfg):
    engine = Engine(rules_cfg)
    engine.step(Level.WARNING, "09:00")
    issued = engine.step(Level.DANGER, "10:00")
    assert [(a.kind, a.level) for a in issued] == [("alert", Level.DANGER)]


def test_back_to_normal_sends_one_all_clear(rules_cfg):
    engine = Engine(rules_cfg)
    engine.step(Level.WARNING, "09:00")
    first = engine.step(Level.NORMAL, "12:00")
    assert [(a.kind, a.level) for a in first] == [("all_clear", Level.NORMAL)]
    assert engine.step(Level.NORMAL, "12:15") == []


def test_watch_does_not_alert_when_only_warning_and_danger_are_alert_levels(rules_cfg):
    engine = Engine({**rules_cfg, "alerts": {**rules_cfg["alerts"], "alert_levels": ["warning", "danger"]}})
    assert engine.step(Level.WATCH, "08:45") == []
    assert engine.step(Level.NORMAL, "09:00") == []


def _hold_cfg(rules_cfg, **alerts_over):
    return {**rules_cfg, "alerts": {**rules_cfg["alerts"], **alerts_over}}


def test_all_clear_is_held_until_the_minimum_alert_duration(rules_cfg):
    engine = Engine(_hold_cfg(rules_cfg, cooldown_min=60, clear_after_min=60))
    assert [a.kind for a in engine.step(Level.WATCH, "09:00")] == ["alert"]
    assert engine.step(Level.NORMAL, "09:15") == []      # 15 min after the alert: stay silent
    assert engine.step(Level.WATCH, "09:30") == []       # still active, not rising: no new alert
    assert engine.step(Level.NORMAL, "09:45") == []
    issued = engine.step(Level.NORMAL, "10:15")           # 75 min after the alert
    assert [(a.kind, a.level) for a in issued] == [("all_clear", Level.NORMAL)]
    assert engine.step(Level.NORMAL, "10:30") == []


def test_continuous_normal_clears_at_the_first_tick_after_the_hold(rules_cfg):
    engine = Engine(_hold_cfg(rules_cfg, cooldown_min=60, clear_after_min=60))
    engine.step(Level.WATCH, "09:00")
    for when in ("09:15", "09:30", "09:45"):
        assert engine.step(Level.NORMAL, when) == []
    assert [a.kind for a in engine.step(Level.NORMAL, "10:00")] == ["all_clear"]


def test_rising_level_during_the_hold_still_alerts(rules_cfg):
    engine = Engine(_hold_cfg(rules_cfg, cooldown_min=60, clear_after_min=60))
    engine.step(Level.WATCH, "09:00")
    assert engine.step(Level.NORMAL, "09:15") == []
    issued = engine.step(Level.WARNING, "09:30")
    assert [(a.kind, a.level) for a in issued] == [("alert", Level.WARNING)]


def test_danger_normal_danger_inside_the_hold_gives_no_all_clear_and_no_repeat(rules_cfg):
    engine = Engine(_hold_cfg(rules_cfg, cooldown_min=60, clear_after_min=60))
    assert [(a.kind, a.level) for a in engine.step(Level.DANGER, "09:00")] == [("alert", Level.DANGER)]
    assert engine.step(Level.NORMAL, "09:15") == []
    assert engine.step(Level.DANGER, "09:30") == []      # same alert still active: no extra push
    assert engine.step(Level.DANGER, "09:45") == []


def test_alert_older_than_the_hold_is_cleared_on_the_first_normal_tick_known_limitation(rules_cfg):
    # The hold counts from the alert's issue time, not from when the street went quiet.
    engine = Engine(_hold_cfg(rules_cfg, cooldown_min=60, clear_after_min=60))
    engine.step(Level.WATCH, "09:00")
    for when in ("09:15", "09:30", "09:45", "10:00", "10:15"):
        engine.step(Level.WATCH, when)
    assert [a.kind for a in engine.step(Level.NORMAL, "10:30")] == ["all_clear"]
    assert [a.kind for a in engine.step(Level.WATCH, "10:45")] == ["alert"]


def test_clear_after_min_must_stay_inside_the_live_recompute_window(rules_cfg):
    with pytest.raises(ValueError):
        alerts.clear_after({"cooldown_min": 60, "clear_after_min": 180})
    assert alerts.clear_after(rules_cfg["alerts"]) < timedelta(minutes=alerts.LIVE_WINDOW_MIN)


def test_missing_clear_after_min_falls_back_to_the_cooldown(rules_cfg):
    alerts_cfg = {k: v for k, v in rules_cfg["alerts"].items() if k != "clear_after_min"}
    engine = Engine({**rules_cfg, "alerts": {**alerts_cfg, "cooldown_min": 45}})
    engine.step(Level.WATCH, "09:00")
    assert engine.step(Level.NORMAL, "09:30") == []
    assert [a.kind for a in engine.step(Level.NORMAL, "09:45")] == ["all_clear"]
