from datetime import datetime

import pandas as pd

from floodready.engine import levels, matrix
from floodready.engine.types import Level, Reason, TriggerResult

T = lambda hhmm: datetime(2024, 11, 12, int(hhmm[:2]), int(hhmm[3:]))  # noqa: E731
RAIN = Reason(code="rain_1h", value=61.5, unit="mm", station="Kg. Perepat, Kapar",
              text_en="61.5 mm of rain in 1 h at Kg. Perepat, Kapar", text_ms="Hujan 61.5 mm dalam 1 jam di Kg. Perepat, Kapar")


def trigger(level, when="09:00", confidence="high"):
    return TriggerResult(level=level, confidence=confidence, fired_by=("rule_rain",) if level else (),
                         reasons=(RAIN,) if level else (), data_time=T(when), stale_stations=())


STREETS = pd.DataFrame({"street_id": ["BBR-a", "BBR-b", "BBR-c"], "susceptibility": [5, 2, 1]})


def test_risk_matrix_examples_from_the_plan(matrix_cfg):
    assert matrix.street_level(5, Level.WARNING, matrix_cfg) is Level.WARNING
    assert matrix.street_level(2, Level.WARNING, matrix_cfg) is Level.WATCH
    assert matrix.street_level(1, Level.WATCH, matrix_cfg) is Level.NORMAL
    assert matrix.street_level(4, Level.DANGER, matrix_cfg) is Level.DANGER


def test_flood_prone_street_gets_warning_with_time_window_and_reasons(rules_cfg, matrix_cfg):
    states = {s.street_id: s for s in levels.street_states(STREETS, trigger(Level.WARNING), rules_cfg, matrix_cfg)}
    a = states["BBR-a"]
    assert a.level is Level.WARNING and a.trigger_level is Level.WARNING
    assert (a.window_start, a.window_end) == (T("09:30"), T("10:30"))
    assert a.reasons[0].text_en == "61.5 mm of rain in 1 h at Kg. Perepat, Kapar"
    assert a.fired_by == ("rule_rain",) and a.confidence == "high" and a.flood_probability is None


def test_less_prone_streets_get_lower_levels_and_no_window(rules_cfg, matrix_cfg):
    states = {s.street_id: s for s in levels.street_states(STREETS, trigger(Level.WARNING), rules_cfg, matrix_cfg)}
    assert states["BBR-b"].level is Level.WATCH and states["BBR-b"].window_start == T("09:30")   # Watch is an alert level now
    assert states["BBR-c"].level is Level.NORMAL


def test_quiet_trigger_keeps_every_street_normal(rules_cfg, matrix_cfg):
    states = levels.street_states(STREETS, trigger(Level.NORMAL), rules_cfg, matrix_cfg)
    assert {s.level for s in states} == {Level.NORMAL}
    assert all(s.reasons == () for s in states)
