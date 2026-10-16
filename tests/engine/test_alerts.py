from datetime import datetime

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
